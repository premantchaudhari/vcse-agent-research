"""Deterministic synthetic-layout transfer ablation for an optional local Ollama planner.

This does not establish real-website generalization or novelty. No network
requests are made by browser fixtures; Ollama (if selected) is loopback-only.
"""
from __future__ import annotations

import argparse
import json
import random
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urljoin

from vcse.browser import BrowserSession, Step, invoice_table_verifier
from vcse.discovery import DiscoveryEngine
from vcse.phase4 import ORIGIN, Case, RecordedPlanner, make_planner

ARMS = ("no-memory", "naive-memory", "verified-memory")
LABELS = ("Records center", "Annual statements", "Transaction history")
ALTERNATES = ("Records archive", "Yearly documents", "Payment activity")
GOAL = "Retrieve all invoices and verify every ID and total"
ROWS = (("INV-101", "120.50"), ("INV-102", "79.50"), ("INV-103", "200.00"))
EXPECTED = {"count": 3, "invoice_ids": [row[0] for row in ROWS], "total": "400.00"}


def table_html(identifier: str, *, corrupt=False) -> str:
    rows = list(ROWS)
    if corrupt:
        rows[-1] = ("INV-103", "201.00")
    content = "".join(f"<tr><td>{key}</td><td>{value}</td></tr>" for key, value in rows)
    return (f'<table id="{identifier}"><thead><tr><th>Invoice ID</th>'
            f"<th>Amount</th></tr></thead><tbody>{content}</tbody></table>")


@dataclass(frozen=True)
class Layout:
    case: Case
    family: int
    variant: str


def make_layout(family: int, variant: str, seed: int = 1307) -> Layout:
    """Layout changes are reproducible, and expected answers never enter observations."""
    if family not in range(len(LABELS)):
        raise ValueError("unknown family")
    if variant not in ("ids", "renamed", "decoy", "corrupt"):
        raise ValueError("unknown variant")
    rng = random.Random(f"{seed}:{family}:{variant}")
    nonce = rng.randrange(100000, 999999)
    link_id = f"route-{nonce}"
    table_id = f"ledger-{nonce}"
    route = f"/records-{nonce}"
    label = ALTERNATES[family] if variant == "renamed" else LABELS[family]
    links = [f'<a id="{link_id}" href="{route}">{label}</a>']
    documents = {ORIGIN + route: "<h1>Verified records</h1>" + table_html(
        table_id, corrupt=variant == "corrupt")}
    if variant == "decoy":
        # Same visible name: a stored label alone is ambiguous and must not be trusted.
        decoy_path = f"/unrelated-{nonce}"
        links.insert(0, f'<a id="trap-{nonce}" href="{decoy_path}">{label}</a>')
        documents[ORIGIN + decoy_path] = (
            "<h1>Unrelated preview</h1>" + table_html("preview", corrupt=True))
    # Noise changes visible layout/element ordering without supplying the answer.
    if rng.randrange(2):
        links.reverse()
    links.insert(0, '<a id="help" href="/help">Help</a>')
    documents[ORIGIN + "/help"] = "<h1>Help</h1><p>Use the records area.</p>"
    documents[ORIGIN] = (
        f"<h1>Workspace {family}</h1><nav>{''.join(links)}</nav>"
        '<button id="export" disabled>Export</button>')
    case = Case(f"f{family}-{variant}-{nonce}", "heldout", GOAL, documents, EXPECTED)
    return Layout(case, family, variant)


def training_case(family: int) -> Case:
    route = f"/source-{family}"
    documents = {
        ORIGIN: (f'<h1>Source workspace</h1><a id="source-link-{family}" '
                 f'href="{route}">{LABELS[family]}</a>'),
        ORIGIN + route: "<h1>Records</h1>" + table_html(f"source-table-{family}"),
    }
    return Case(f"train-{family}", "development", GOAL, documents, EXPECTED)


def browser(case: Case) -> BrowserSession:
    return BrowserSession({ORIGIN}, timeout_ms=1200, fixture_documents=case.documents)


def observe(case: Case, path: list[Step]) -> dict:
    return browser(case).run(path + [Step("inspect", "", "observation")])["data"]["observation"]


def verify_plan(case: Case, steps: list[Step]) -> bool:
    """Independently verify the full result; exceptions never count as success."""
    try:
        result = browser(case).run(steps)
        return invoice_table_verifier(result, case.expected)
    except Exception:
        return False


def learned_skill(case: Case, planner) -> tuple[dict | None, int]:
    """Train with the same planner as baseline; independently verify before storing."""
    tracked = RecordedPlanner(planner)
    report = DiscoveryEngine(browser(case), tracked, ORIGIN, case.expected, max_attempts=5).execute(case.goal)
    if not (report.status == "completed" and report.verified):
        return None, tracked.calls
    actions = [item for item in report.attempts
               if item.get("state") in ("executed", "verified")]
    if len(actions) != 2 or [a["action"] for a in actions] != ["click", "extract_table"]:
        return None, tracked.calls
    source = observe(case, [Step("navigate", ORIGIN)])
    link = next((x for x in source["links"] if x["selector"] == actions[0]["target"]), None)
    if not link:
        return None, tracked.calls
    steps = [Step("navigate", ORIGIN),
             Step("click", actions[0]["target"]),
             Step("extract_table", actions[1]["target"], "invoices")]
    if not verify_plan(case, steps):
        return None, tracked.calls
    return {"selector": actions[0]["target"], "table_selector": actions[1]["target"],
            "link_text": link["text"], "source_case": case.case_id}, tracked.calls


def attempt_memory(case: Case, skill: dict, arm: str) -> tuple[bool, str]:
    """No model calls on a memory hit. Reject ambiguity and verify every result."""
    if arm == "naive-memory":
        selected = skill["selector"]
        table_selector = skill["table_selector"]
    elif arm == "verified-memory":
        start = observe(case, [Step("navigate", ORIGIN)])
        # Exact-label identity is deliberately conservative; no oracle-based selection.
        matching = [x for x in start["links"] if x.get("text", "").strip().casefold()
                    == skill["link_text"].strip().casefold() and x.get("selector")]
        if len(matching) != 1:
            return False, "ambiguous_or_missing_label"
        selected = matching[0]["selector"]
        target = urljoin(ORIGIN + "/", matching[0].get("href", ""))
        if target not in case.documents or target == ORIGIN:
            return False, "unapproved_destination"
        middle = observe(case, [Step("navigate", ORIGIN), Step("click", selected)])
        tables = [t for t in middle["tables"] if t.get("headers") == ["Invoice ID", "Amount"]
                  and t.get("selector")]
        if len(tables) != 1:
            return False, "ambiguous_or_missing_table"
        table_selector = tables[0]["selector"]
    else:
        raise ValueError("unknown memory arm")
    steps = [Step("navigate", ORIGIN), Step("click", selected),
             Step("extract_table", table_selector, "invoices")]
    if verify_plan(case, steps):
        return True, "verified_reuse"
    return False, "replay_failed_verification"


def evaluate(case: Case, arm: str, skill: dict | None, planner) -> dict:
    start = time.monotonic()
    reuse_attempted = arm != "no-memory" and skill is not None
    reason = None
    if reuse_attempted:
        try:
            ok, reason = attempt_memory(case, skill, arm)
        except Exception:
            ok, reason = False, "replay_exception"
        if ok:
            return {"case_id": case.case_id, "arm": arm, "verified": True,
                    "planner_calls": 0, "memory_attempted": True, "memory_reused": True,
                    "memory_result": reason, "elapsed_seconds": round(time.monotonic()-start, 3)}
    tracked = RecordedPlanner(planner)
    report = DiscoveryEngine(browser(case), tracked, ORIGIN, case.expected, max_attempts=5).execute(case.goal)
    return {"case_id": case.case_id, "arm": arm,
            "verified": report.status == "completed" and report.verified,
            "planner_calls": tracked.calls, "memory_attempted": reuse_attempted,
            "memory_reused": False, "memory_result": reason,
            "gap": report.gap, "elapsed_seconds": round(time.monotonic()-start, 3)}


def summarize(rows: list[dict], arm: str) -> dict:
    group = [r for r in rows if r["arm"] == arm]
    return {"arm": arm, "tasks": len(group),
            "verified_successes": sum(r["verified"] for r in group),
            "planner_calls": sum(r["planner_calls"] for r in group),
            "memory_hits": sum(r["memory_reused"] for r in group),
            "seconds": round(sum(r["elapsed_seconds"] for r in group), 3)}


def run(planner_factory, variants=("ids", "renamed", "decoy", "corrupt"),
        families=(0, 1, 2), seed=1307, arms=ARMS, output=None, replicates=1) -> dict:
    """One pre-trained skill per family; all arms share that skill and test layouts."""
    if not 1 <= replicates <= 10:\n        raise ValueError("replicates must be 1..10")\n    if any(a not in ARMS for a in arms):
        raise ValueError("invalid arm")
    if len(set(arms)) != len(arms):
        raise ValueError("duplicate arms")
    skills = {}
    training_calls = 0
    for family in families:
        skill, calls = learned_skill(training_case(family), planner_factory())
        skills[family] = skill
        training_calls += calls
    cases = [make_layout(family, variant, seed + copy * 1009)\n             for copy in range(replicates)\n             for family in families for variant in variants]
    # Pair all arms on the same case in a deterministic randomized order.
    rng = random.Random(seed)
    rng.shuffle(cases)
    results = []
    for layout in cases:
        order = list(arms)
        rng.shuffle(order)
        for arm in order:
            row = evaluate(layout.case, arm, skills[layout.family], planner_factory())
            row["family"] = layout.family
            row["variant"] = layout.variant
            results.append(row)
            print(f"{row['case_id']} {arm}: verified={row['verified']} "
                  f"calls={row['planner_calls']} reuse={row['memory_reused']}", flush=True)
    report = {
        "protocol": "synthetic-layout-transfer-v0.1",
        "warning": "Synthetic fixtures only; no real-site generalization demonstrated.",
        "seed": seed, "replicates": replicates, "training_model_calls": training_calls,
        "trained_families": sum(v is not None for v in skills.values()),
        "families": list(families), "variants": list(variants),
        "arms": list(arms), "summary": [summarize(results, arm) for arm in arms],
        "results": results,
    }
    if output:
        target = Path(output)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


class FixturePlanner:
    """Explicit deterministic test double; never label its results as model results."""
    def propose(self, goal, observation, failed, home):
        tables = [t for t in observation.get("tables", [])
                  if t.get("headers") == ["Invoice ID", "Amount"]]
        if tables:
            return {"action": "extract_table", "selector": tables[0]["selector"]}
        links = [l for l in observation.get("links", []) if l.get("selector")
                 and any(k in l["text"].lower()
                         for k in ("records", "statements", "transaction", "yearly", "payment"))]
        if links:
            return {"action": "click", "selector": links[-1]["selector"]}
        return {"action": "stop", "selector": ""}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--planner", choices=("ollama", "fixture"), default="ollama")
    parser.add_argument("--seed", type=int, default=1307)\n    parser.add_argument("--replicates", type=int, default=1,\n                        help="4 gives 48 test layouts (3 families x 4 variants x 4)")
    parser.add_argument("--variants", nargs="+", choices=("ids", "renamed", "decoy", "corrupt"),
                        default=["ids", "renamed", "decoy", "corrupt"])
    parser.add_argument("--families", nargs="+", type=int, choices=(0, 1, 2), default=[0, 1, 2])
    parser.add_argument("--output", default="artifacts/transfer-ablation.json")
    args = parser.parse_args()
    def factory():
        if args.planner == "fixture":
            return FixturePlanner()
        return make_planner("model")
    result = run(factory, variants=args.variants, families=args.families,
                 seed=args.seed, output=args.output, replicates=args.replicates)
    print(json.dumps({"planner": args.planner, "summary": result["summary"],
                      "training_model_calls": result["training_model_calls"]}, indent=2))


if __name__ == "__main__":
    main()
