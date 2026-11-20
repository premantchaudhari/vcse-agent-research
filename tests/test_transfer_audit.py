"""Tests of reporting safeguards; no browser or model needed."""
import json
import tempfile
import unittest
from pathlib import Path

from vcse.transfer_audit import audit_reports, classify_failure


def result(case, variant, arm, verified, calls=1, **kwargs):
    row = {"case_id": case, "variant": variant, "arm": arm,
           "verified": verified, "planner_calls": calls,
           "elapsed_seconds": 1.0, "memory_reused": False}
    row.update(kwargs)
    return row


class TransferAuditTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "run.json"

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, rows, trained=1, seed=1307):
        self.path.write_text(json.dumps({
            "protocol": "synthetic-layout-transfer-v0.1",
            "seed": seed, "families": [0], "variants": ["ids", "corrupt"],
            "replicates": 1,
            "trained_families": trained, "training_model_calls": 2,
            "results": rows,
        }))
        return self.path

    def test_positive_and_safety_denominators_are_separate(self):
        rows = []
        for arm in ("no-memory", "naive-memory", "verified-memory"):
            rows.append(result("a", "ids", arm, arm == "verified-memory",
                               memory_reused=arm == "verified-memory"))
            rows.append(result("b", "corrupt", arm, False, gap="attempt_budget_exhausted"))
        audit = audit_reports([self.write(rows)])
        verified = audit["arms"]["verified-memory"]
        self.assertEqual((verified["positive_verified"], verified["positive_trials"]), (1, 1))
        self.assertEqual((verified["negative_rejected"], verified["negative_trials"]), (1, 1))
        self.assertEqual(verified["actual_memory_hits"], 1)
        self.assertEqual(audit["paired_positive_outcomes"]["verified-memory"]["candidate_only_succeeded"], 1)

    def test_false_positive_on_corrupt_is_reported_not_hidden(self):
        rows = []
        for arm in ("no-memory", "naive-memory", "verified-memory"):
            rows += [result("a", "ids", arm, True),
                     result("b", "corrupt", arm, arm == "verified-memory")]
        audit = audit_reports([self.write(rows)])
        self.assertEqual(audit["arms"]["verified-memory"]["unsafe_false_positives"], 1)
        self.assertEqual(audit["arms"]["verified-memory"]["negative_rejected"], 0)

    def test_failed_training_flagged(self):
        rows = [result("a", "ids", arm, True)
                for arm in ("no-memory", "naive-memory", "verified-memory")]
        audit = audit_reports([self.write(rows, trained=0)])
        self.assertFalse(audit["training"][0]["training_success"])
        self.assertEqual(audit["training_failed_reports"], 1)

    def test_missing_pair_rejected(self):
        with self.assertRaisesRegex(ValueError, "incomplete paired"):
            audit_reports([self.write([result("a", "ids", "no-memory", True)])])

    def test_duplicate_pair_rejected(self):
        rows = [result("a", "ids", arm, False)
                for arm in ("no-memory", "naive-memory", "verified-memory")]
        with self.assertRaisesRegex(ValueError, "duplicate case/arm"):
            audit_reports([self.write(rows + rows[:1])])

    def test_classify_model_and_browser_failures(self):
        self.assertEqual(classify_failure({"verified": False, "gap": "planner_error: invalid JSON"}),
                         "planner_error")
        self.assertEqual(classify_failure({"verified": False, "gap": "observation_failed: Locator.click: Timeout"}),
                         "browser_execution_error")
        self.assertEqual(classify_failure({"verified": False, "gap": "selector_not_observed"}),
                         "selector_not_observed")


if __name__ == "__main__":
    unittest.main()
