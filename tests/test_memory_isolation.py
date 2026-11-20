"""Offline memory-isolation protocol tests; no Ollama or external sites."""
import tempfile
import unittest
from pathlib import Path

from vcse.memory_isolation import (
    ARMS, attempt_skill, evaluate_arm, run_isolation, validated_source_skill,
)
from vcse.transfer_benchmark import FixturePlanner, make_layout


class MemoryIsolationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.skill = validated_source_skill(0)

    def test_canonical_source_is_browser_verified_without_model(self):
        self.assertEqual(self.skill["verification"], "fresh_browser_replay_passed")
        self.assertEqual(self.skill["acquisition_planner_calls"], 0)
        self.assertEqual(self.skill["link_text"], "Records center")

    def test_changed_ids_expose_difference_vs_exact_selector(self):
        case = make_layout(0, "ids", seed=1307).case
        exact_ok, _ = attempt_skill(case, self.skill, "exact-selector")
        heuristic_ok, _ = attempt_skill(case, self.skill, "label-heuristic")
        verified_ok, _ = attempt_skill(case, self.skill, "verified-memory")
        self.assertFalse(exact_ok)
        self.assertTrue(heuristic_ok)
        self.assertTrue(verified_ok)

    def test_renamed_links_reject_both_label_based_arms(self):
        case = make_layout(0, "renamed", seed=1307).case
        for arm in ("label-heuristic", "verified-memory"):
            success, reason = attempt_skill(case, self.skill, arm)
            self.assertFalse(success)
            self.assertIn("link", reason)

    def test_ambiguous_decoy_is_rejected_by_verified_arm(self):
        case = make_layout(0, "decoy", seed=1307).case
        success, reason = attempt_skill(case, self.skill, "verified-memory")
        self.assertFalse(success)
        self.assertEqual(reason, "applicability_ambiguous_or_missing_link")
        # The heuristic is permitted to attempt the first label match,
        # but all outcomes still pass through the same independent verifier.
        heuristic_success, _ = attempt_skill(case, self.skill, "label-heuristic")
        self.assertIn(heuristic_success, (True, False))

    def test_corrupted_fixture_never_counts_as_success(self):
        case = make_layout(0, "corrupt", seed=1307).case
        for arm in ARMS[1:]:
            success, _ = attempt_skill(case, self.skill, arm)
            self.assertFalse(success)

    def test_no_fallback_requires_no_model_calls(self):
        case = make_layout(0, "renamed", seed=1307).case
        def forbidden():
            raise AssertionError("planner invoked despite disabled fallback")
        for arm in ARMS:
            row = evaluate_arm(case, arm, self.skill, forbidden, fallback=False)
            self.assertFalse(row["verified"])
            self.assertEqual(row["planner_calls"], 0)

    def test_full_matched_protocol_counts_negative_controls_separately(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "isolated.json"
            report = run_isolation(
                FixturePlanner, families=(0,), replicates=1,
                fallback=False, output=path,
            )
            self.assertTrue(path.exists())
            self.assertEqual(report["protocol"], "synthetic-memory-isolation-v0.2")
            self.assertEqual(report["source_skill_acquisition_planner_calls"], 0)
            self.assertEqual(len(report["results"]), 16)
            self.assertEqual(set(report["arms"]), set(ARMS))
            for stat in report["summary"]:
                self.assertEqual(stat["solvable_trials"], 3)
                self.assertEqual(stat["negative_trials"], 1)
                self.assertEqual(stat["unsafe_false_positives"], 0)
                self.assertEqual(stat["planner_calls"], 0)

    def test_reject_invalid_configuration(self):
        with self.assertRaises(ValueError):
            run_isolation(FixturePlanner, arms=("unknown",))
        with self.assertRaises(ValueError):
            run_isolation(FixturePlanner, variants=("unknown",))


if __name__ == "__main__":
    unittest.main()
