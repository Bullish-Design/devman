"""Tests for semantic-promotion orchestration and preservation."""

from __future__ import annotations

import asyncio
import unittest

from promotion_probe import run_suite


class PromotionStateMachineTests(unittest.TestCase):
    """Require every expected decision and preservation invariant."""

    def test_success_and_adversarial_matrices(self) -> None:
        results = asyncio.run(run_suite())
        self.assertTrue(results["suite_passed"], results["metrics"])
        self.assertEqual(results["metrics"]["expected_acceptances"], 10)
        self.assertEqual(results["metrics"]["expected_rejections"], 9)
        self.assertEqual(results["metrics"]["false_acceptances"], 0)
        self.assertEqual(results["metrics"]["false_rejections"], 0)
        self.assertEqual(
            set(results["success_cases"]),
            {
                "behavior",
                "body",
                "delete",
                "docstring",
                "import",
                "merge",
                "move",
                "rename",
                "signature",
                "split",
            },
        )
        self.assertEqual(
            set(results["rejection_cases"]),
            {
                "cancel",
                "contradictory",
                "hallucinated",
                "malformed",
                "nonconvergent",
                "partial",
                "stale",
                "timeout",
                "undeclared-source-field",
            },
        )

        for result in results["success_cases"].values():
            self.assertTrue(result["accepted"])
            self.assertEqual(result["terminal_state"], "accepted")
            self.assertTrue(result["edited_source_preserved"])
            self.assertFalse(result["accepted_store_preserved"])
            self.assertEqual(result["source_before_hash"], result["source_after_hash"])
            self.assertNotEqual(result["store_before_hash"], result["store_after_hash"])

        for result in results["rejection_cases"].values():
            self.assertFalse(result["accepted"])
            self.assertTrue(result["edited_source_preserved"])
            self.assertTrue(result["accepted_store_preserved"])
            self.assertEqual(result["source_before_hash"], result["source_after_hash"])
            self.assertEqual(result["store_before_hash"], result["store_after_hash"])

        self.assertEqual(
            results["rejection_cases"]["stale"]["terminal_state"],
            "rejected-stale-input",
        )
        self.assertEqual(
            results["rejection_cases"]["cancel"]["terminal_state"],
            "rejected-cancelled",
        )
        for name in set(results["rejection_cases"]) - {"stale", "cancel"}:
            self.assertEqual(
                results["rejection_cases"][name]["terminal_state"],
                "rejected-attempt-limit",
            )


if __name__ == "__main__":
    unittest.main()
