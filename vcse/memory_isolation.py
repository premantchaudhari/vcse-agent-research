"""Four-arm memory isolation benchmark on reproducible, in-memory browser fixtures.

This isolates memory-applicability rules using ONE independently validated,
canonical source skill. It is not a claim of semantic generalization.
'fixture' means deterministic test double, never a Qwen benchmark result.
"""
from __future__ import annotations

import argparse
import json
import random
import time
from pathlib import Path
from urllib.parse import urljoin

from vcse.browser import Step
from vcse.discovery import DiscoveryEngine
from vcse.phase4 import ORIGIN, RecordedPlanner, make_planner
from vcse.transfer_benchmark import (
    LABELS, FixturePlanner, browser, make_layout, observe,
    summarize, training_case, verify_plan,
)

ARMS = ("no-memory", "exact-selector", "label-heuristic", "verified-memory")
VARIANTS = ("ids", "renamed", "decoy", "corrupt")
NEGATIVE_VARIANTS = frozenset({"corrupt"})


def validated_source_skill(family: int) -> dict:
    """Construct canonical source skill, verify in an actual browser, then freeze it.

    Skill acquisition uses NO model calls for any arm. We intentionally isolate
    retrieval/applicability from the separate question of model-based learning.
    The source selectors/label are from the training fixture only. Never look at
    held-out test cases to build skills.
    """
    source = training_case(family)
    steps = [
        Step("navigate", ORIGIN),
        Step("click", f"#source-link-{family}"),
        Step("extract_table", f"#source-table-{family}", "invoices"),
    ]
    if not verify_plan(source, steps):
        raise RuntimeError(f"canonical source skill failed verification: family {family}")
    root = observe(source, [Step("navigate", ORIGIN)])
    matched = [x for x in root["links"]
               if x.get("selector") == f"#source-link-{family}"]
    if len(matched) != 1 or matched[0].get("text") != LABELS[family]:
        raise RuntimeError("training skill observation mismatch")
    return {
        "source_case_id": source.case_id,
        "selector": f"#source-link-{family}",
        "table_selector": f"#source-table-{family}",
        "link_text": matched[0]["text"],
        "verification": "fresh_browser_replay_passed",
        "acquisition": "deterministic_canonical_source",
        "acquisition_planner_calls": 0,
    }


def _observed_link_matches(case, skill):
    root = observe(case, [Step("navigate", ORIGIN)])
    return [x for x in root["links"] if x.get("selector")
            and x.get("text", "").strip().casefold()
            == skill["link_text"].strip().casefold()]


def _allowed_destination(case, link):
    target = urljoin(ORIGIN + "/", link.get("href", ""))
    return target in case.documents and target != ORIGIN


def attempt_skill(case, skill: dict, arm: str) -> tuple[bool, str]:
    """One zero-model-call memory attempt, with common final task verifier.

    The heuristic deliberately uses the FIRST matching link and FIRST table,
    while the verified arm rejects ambiguous links/tables and checks schema.
    None of these shortcuts may override the independent invoice verifier.
    """
    if arm == "exact-selector":
        link_selector = skill["selector"]
        table_selector = skill["table_selector"]
    elif arm in ("label-heuristic", "verified-memory"):
        links = _observed_link_matches(case, skill)
        if arm == "verified-memory":
            if len(links) != 1:
                return False, "applicability_ambiguous_or_missing_link"
            link = links[0]
        else:
            if not links:
                return False, "heuristic_missing_link"
            link = links[0]
        if not _allowed_destination(case, link):
            return False, "destination_not_in_fixture_allowlist"
        link_selector = link["selector"]
        next_observation = observe(
            case, [Step("navigate", ORIGIN), Step("click", link_selector)])
        if arm == "verified-memory":
            tables = [t for t in next_observation["tables"]
                      if t.get("selector") and t.get("headers") == ["Invoice ID", "Amount"]]
            if len(tables) != 1:
                return False, "applicability_ambiguous_or_missing_table"
        else:
            tables = [t for t in next_observation["tables"] if t.get("selector")]
            if not tables:
                return False, "heuristic_missing_table"
        table_selector = tables[0]["selector"]
    else:
        raise ValueError("unknown memory arm")
    steps = [Step("navigate", ORIGIN), Step("click", link_selector),
             Step("extract_table", table_selector, "invoices")]
    return ((True, "independently_verified_reuse")
            if verify_plan(case, steps)
            else (False, "memory_replay_failed_independent_verification"))


def evaluate_arm(case, arm: str, skill: dict, planner_factory,
                 *, fallback=True) -> dict:
    if arm not in ARMS:
        raise ValueError("invalid arm")
    start = time.monotonic()
    memory_attempted = arm != "no-memory"
    memory_status = "not_applicable"
    memory_seconds = 0.0
    if memory_attempted:
        begun = time.monotonic()
        try:
            reused, memory_status = attempt_skill(case, skill, arm)
        except Exception as exc:
            # Distinguish browser or fixture errors from applicability decisions.
            reused = False
            memory_status = "memory_exception:" + type(exc).__name__
        memory_seconds = time.monotonic() - begun
        if reused:
            return {
                "case_id": case.case_id, "arm": arm, "verified": True,
                "planner_calls": 0, "memory_attempted": True,
                "memory_reused": True, "memory_status": memory_status,
                "fallback_used": False, "gap": None,
                "memory_seconds": round(memory_seconds, 3),
                "elapsed_seconds": round(time.monotonic() - start, 3),
            }
    if not fallback:
        return {
            "case_id": case.case_id, "arm": arm, "verified": False,
            "planner_calls": 0, "memory_attempted": memory_attempted,
            "memory_reused": False, "memory_status": memory_status,
            "fallback_used": False, "gap": "fallback_disabled",
            "memory_seconds": round(memory_seconds, 3),
            "elapsed_seconds": round(time.monotonic() - start, 3),
        }
    planner = RecordedPlanner(planner_factory())
    report = DiscoveryEngine(
        browser(case), planner, ORIGIN, case.expected, max_attempts=5
    ).execute(case.goal)
    return {
        "case_id": case.case_id, "arm": arm,
        "verified": report.status == "completed" and report.verified,
        "planner_calls": planner.calls,
        "memory_attempted": memory_attempted, "memory_reused": False,
        "memory_status": memory_status, "fallback_used": memory_attempted,
        "gap": report.gap, "memory_seconds": round(memory_seconds, 3),
        "elapsed_seconds": round(time.monotonic() - start, 3),
    }


def summarise_isolation(results: list[dict], arm: str) -> dict:
    all_rows = [r for r in results if r["arm"] == arm]
    positives = [r for r in all_rows if r["variant"] not in NEGATIVE_VARIANTS]
    negative = [r for r in all_rows if r["variant"] in NEGATIVE_VARIANTS]
    base = summarize(results, arm)
    base.update({
        "solvable_verified": sum(bool(r["verified"]) for r in positives),
        "solvable_trials": len(positives),
        "negative_rejected": sum(not r["verified"] for r in negative),
        "negative_trials": len(negative),
        "unsafe_false_positives": sum(bool(r["verified"]) for r in negative),
        "fallback_count": sum(bool(r["fallback_used"]) for r in all_rows),
        "memory_seconds": round(sum(r["memory_seconds"] for r in all_rows), 3),
    })
    return base


def run_isolation(planner_factory, *, families=(0, 1, 2),
                  variants=VARIANTS, replicates=1, seed=1307,
                  arms=ARMS, output=None, fallback=True) -> dict:
    if not 1 <= replicates <= 10:
        raise ValueError("replicates must be 1..10")
    if not families or not variants or not arms:
        raise ValueError("families, variants and arms must be nonempty")
    if any(a not in ARMS for a in arms) or len(set(arms)) != len(arms):
        raise ValueError("invalid or duplicate arms")
    if any(v not in VARIANTS for v in variants):
        raise ValueError("invalid variants")

    # Fail the experiment instead of quietly treating missing memory as no memory.
    skills = {family: validated_source_skill(family) for family in families}
    cases = [make_layout(family, variant, seed + copy * 1009)
             for copy in range(replicates)
             for family in families for variant in variants]
    rng = random.Random(seed)
    rng.shuffle(cases)
    results = []
    for item in cases:
        order = list(arms)
        rng.shuffle(order)
        for arm in order:
            row = evaluate_arm(item.case, arm, skills[item.family],
                               planner_factory, fallback=fallback)
            row.update({"family": item.family, "variant": item.variant})
            results.append(row)
            print(f"{row['case_id']} {arm}: verified={row['verified']} "
                  f"calls={row['planner_calls']} reuse={row['memory_reused']} "
                  f"memory={row['memory_status']}", flush=True)
    report = {
        "protocol": "synthetic-memory-isolation-v0.2",
        "scope": "synthetic_fixture_only",
        "note": "Canonical skills were independently validated once per family; "
                "no model trained a skill. This isolates applicability, NOT learning.",
        "seed": seed, "families": list(families),
        "variants": list(variants), "replicates": replicates,
        "arms": list(arms), "source_skill_count": len(skills),
        "source_skill_acquisition_planner_calls": 0,
        "same_validated_skill_for_all_memory_arms": True,
        "fallback_enabled": fallback,
        "summary": [summarise_isolation(results, arm) for arm in arms],
        "results": results,
    }
    if output:
        destination = Path(output)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--planner", choices=("ollama", "fixture"), default="ollama")
    parser.add_argument("--families", nargs="+", type=int, choices=(0, 1, 2),
                        default=[0, 1, 2])
    parser.add_argument("--variants", nargs="+", choices=VARIANTS, default=list(VARIANTS))
    parser.add_argument("--seed", type=int, default=1307)
    parser.add_argument("--replicates", type=int, default=1)
    parser.add_argument("--no-fallback", action="store_true",
                        help="Isolate memory-only hits; no local-model inference")
    parser.add_argument("--output", default="artifacts/memory-isolation.json")
    args = parser.parse_args()
    def factory():
        return FixturePlanner() if args.planner == "fixture" else make_planner("model")
    result = run_isolation(
        factory, families=args.families, variants=args.variants,
        replicates=args.replicates, seed=args.seed,
        output=args.output, fallback=not args.no_fallback,
    )
    print(json.dumps({"planner": args.planner, "scope": result["scope"],
                      "summary": result["summary"]}, indent=2))


if __name__ == "__main__":
    main()
