"""Offline protocol tests; no model API or secrets required."""
import tempfile
import unittest
from pathlib import Path

from vcse.transfer_benchmark import (
    ARMS, FixturePlanner, attempt_memory, learned_skill,
    make_layout, run, summarize, training_case,
)


class TransferBenchmarkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.skill, cls.calls = learned_skill(training_case(0), FixturePlanner())

    def test_training_is_independently_verified(self):
        self.assertIsNotNone(self.skill)
        self.assertGreaterEqual(self.calls, 2)
        self.assertEqual(self.skill["link_text"], "Records center")

    def test_unseen_selector_ids_reuse_only_in_verified_arm(self):
        case = make_layout(0, "ids").case
        self.assertNotIn(self.skill["selector"], case.documents[case.case_id] if case.case_id in case.documents else case.documents[next(iter(case.documents))])
        ok, reason = attempt_memory(case, self.skill, "verified-memory")
        self.assertTrue(ok, reason)
        raw_ok, raw_reason = attempt_memory(case, self.skill, "naive-memory")
        self.assertFalse(raw_ok)
        self.assertEqual(raw_reason, "replay_failed_verification")

    def test_renamed_label_fails_closed(self):
        ok, reason = attempt_memory(make_layout(0, "renamed").case, self.skill, "verified-memory")
        self.assertFalse(ok)
        self.assertEqual(reason, "ambiguous_or_missing_label")

    def test_duplicate_label_fails_closed(self):
        ok, reason = attempt_memory(make_layout(0, "decoy").case, self.skill, "verified-memory")
        self.assertFalse(ok)
        self.assertEqual(reason, "ambiguous_or_missing_label")

    def test_bad_table_does_not_verify(self):
        ok, reason = attempt_memory(make_layout(0, "corrupt").case, self.skill, "verified-memory")
        self.assertFalse(ok)
        self.assertEqual(reason, "replay_failed_verification")

    def test_fixture_is_deterministic_and_seeded(self):
        one = make_layout(1, "ids", seed=9).case
        two = make_layout(1, "ids", seed=9).case
        other = make_layout(1, "ids", seed=10).case
        self.assertEqual(one.documents, two.documents)
        self.assertNotEqual(one.documents, other.documents)

    def test_full_three_arm_protocol_records_all_results(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "report.json"
            result = run(FixturePlanner, families=(0,), variants=("ids", "renamed", "decoy", "corrupt"),
                         output=str(path))
            self.assertEqual(len(result["results"]), 12)
            self.assertEqual(set(result["arms"]), set(ARMS))
            self.assertEqual(len(result["summary"]), 3)
            self.assertEqual(result["training_model_calls"], 2)
            self.assertEqual(sum(s["tasks"] for s in result["summary"]), 12)
            self.assertTrue(path.exists())
            self.assertTrue(all("planner_calls" in r for r in result["results"]))

    def test_invalid_arm_is_rejected(self):
        with self.assertRaises(ValueError):
            run(FixturePlanner, arms=("fictional",))

if __name__ == "__main__":
    unittest.main()
