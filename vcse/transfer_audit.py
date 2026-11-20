"""Audit local transfer-ablation JSON files without running a planner.

All displayed results are descriptive, not statistical significance claims.
Negative controls (corrupt invoice totals) must never be counted as
ordinary solvable-task failures.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

ARMS = ("no-memory", "naive-memory", "verified-memory")
NEGATIVE_VARIANTS = {"corrupt"}


def classify_failure(row: dict) -> str:
    if row.get("verified"):
        return "verified_success"
    gap = str(row.get("gap") or "")
    if "planner_error:" in gap or "invalid JSON" in gap:
        return "planner_error"
    if "observation_failed:" in gap or "TimeoutError:" in gap or "Locator.click:" in gap:
        return "browser_execution_error"
    if "selector_not_observed" in gap:
        return "selector_not_observed"
    if "table_not_observed" in gap:
        return "table_not_observed"
    if "attempt_budget_exhausted" in gap:
        return "attempt_budget_exhausted"
    if "verification" in gap:
        return "verification_failure"
    if gap:
        return "other_failure"
    return "unattributed_failure"


def audit_reports(paths: list[str | Path]) -> dict:
    if not paths:
        raise ValueError("at least one report is required")
    reports = []
    keys = set()
    for path in paths:
        p = Path(path)
        raw = json.loads(p.read_text(encoding="utf-8"))
        if raw.get("protocol") != "synthetic-layout-transfer-v0.1":
            raise ValueError(f"{p}: not a supported transfer ablation report")
        rows = raw.get("results")
        if not isinstance(rows, list) or not rows:
            raise ValueError(f"{p}: missing results")
        seen = set()
        for row in rows:
            if row.get("arm") not in ARMS:
                raise ValueError(f"{p}: unrecognized arm")
            key = (row.get("case_id"), row.get("arm"))
            if key in seen:
                raise ValueError(f"{p}: duplicate case/arm {key}")
            seen.add(key)
        for case_id in {r.get("case_id") for r in rows}:
            arms = {r["arm"] for r in rows if r.get("case_id") == case_id}
            if arms != set(ARMS):
                raise ValueError(f"{p}: incomplete paired arms for {case_id}")
        seed_key = (raw.get("seed"), tuple(raw.get("families", ())),
                    tuple(raw.get("variants", ())), raw.get("replicates", 1))
        if seed_key in keys:
            raise ValueError(f"{p}: duplicate run metadata {seed_key}")
        keys.add(seed_key)
        reports.append({"path": str(p), "raw": raw})
    arm_stats = {}
    for arm in ARMS:
        rows = [r for report in reports for r in report["raw"]["results"]
                if r["arm"] == arm]
        positive = [r for r in rows if r.get("variant") not in NEGATIVE_VARIANTS]
        negative = [r for r in rows if r.get("variant") in NEGATIVE_VARIANTS]
        arm_stats[arm] = {
            "positive_verified": sum(bool(r.get("verified")) for r in positive),
            "positive_trials": len(positive),
            "negative_rejected": sum(not bool(r.get("verified")) for r in negative),
            "negative_trials": len(negative),
            "unsafe_false_positives": sum(bool(r.get("verified")) for r in negative),
            "planner_calls": sum(int(r.get("planner_calls", 0)) for r in rows),
            "total_seconds": round(sum(float(r.get("elapsed_seconds", 0)) for r in rows), 3),
            "actual_memory_hits": sum(bool(r.get("memory_reused")) for r in rows),
            "failures_by_type": dict(sorted(Counter(classify_failure(r) for r in rows
                                 if not r.get("verified")).items())),
        }
    trained_reports = [r for r in reports if int(r["raw"].get("trained_families", 0)) > 0]
    untrained_reports = [r for r in reports if int(r["raw"].get("trained_families", 0)) == 0]
    paired = {}
    for arm in ("naive-memory", "verified-memory"):
        win = loss = tie = 0
        for report in reports:
            by_case = {}
            for row in report["raw"]["results"]:
                if row.get("variant") in NEGATIVE_VARIANTS:
                    continue
                by_case.setdefault(row["case_id"], {})[row["arm"]] = bool(row.get("verified"))
            for outcomes in by_case.values():
                baseline = outcomes["no-memory"]
                candidate = outcomes[arm]
                if candidate and not baseline:
                    win += 1
                elif baseline and not candidate:
                    loss += 1
                else:
                    tie += 1
        paired[arm] = {"candidate_only_succeeded": win,
                       "no_memory_only_succeeded": loss, "same_result": tie}
    training = []
    for r in reports:
        raw = r["raw"]
        training.append({"file": r["path"], "seed": raw.get("seed"),
                         "trained_families": raw.get("trained_families"),
                         "requested_families": len(raw.get("families", [])),
                         "training_planner_calls": raw.get("training_model_calls"),
                         "training_success": raw.get("trained_families") ==
                                             len(raw.get("families", []))})
    return {
        "scope": "synthetic_layout_transfer_only",
        "reports": len(reports),
        "training": training,
        "training_successful_reports": len(trained_reports),
        "training_failed_reports": len(untrained_reports),
        "arms": arm_stats,
        "paired_positive_outcomes": paired,
        "interpretation_limits": [
            "A rejected corrupt fixture is a negative safety control, not an ordinary success.",
            "Runs without a trained skill cannot measure memory transfer.",
            "Differences in independent local-model calls and browser behavior are not causal proof.",
            "No statistical significance, real-website transfer or novelty is established.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("files", nargs="+", help="Existing transfer-qwen-*.json reports")
    parser.add_argument("--output", help="Optional JSON audit output")
    args = parser.parse_args()
    result = audit_reports(args.files)
    formatted = json.dumps(result, indent=2, ensure_ascii=False)
    if args.output:
        path = Path(args.output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(formatted + "\n", encoding="utf-8")
    print(formatted)


if __name__ == "__main__":
    main()
