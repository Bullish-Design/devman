"""Tests for the categorized Python preservation and rejection corpus."""

from __future__ import annotations

import unittest

from python_corpus_probe import run_suite


class PythonCorpusTests(unittest.TestCase):
    def test_corpus_preserves_bytes_and_rejects_before_mutation(self) -> None:
        results = run_suite()
        self.assertTrue(results["suite_passed"], results["metrics"])
        metrics = results["metrics"]
        self.assertEqual(metrics["case_count"], 16)
        self.assertGreaterEqual(metrics["category_count"], 50)
        self.assertEqual(metrics["byte_identity_failures"], 0)
        self.assertEqual(metrics["parse_classification_failures"], 0)
        self.assertEqual(metrics["span_failures"], 0)
        self.assertEqual(metrics["pre_mutation_rejections"], 3)
        self.assertEqual(
            metrics["decisions"],
            {"preserve": 5, "own": 7, "collate": 1, "reject": 3},
        )

        for row in results["cases"]:
            if row["decision"] != "reject":
                self.assertTrue(row["assembly_attempted"])
                self.assertGreater(row["segment_count"], 0)
                self.assertEqual(row["input_hash"], row["output_hash"])

        invalid = next(
            row for row in results["cases"] if row["name"] == "invalid-edited-buffer"
        )
        self.assertFalse(invalid["actual_parse_clean"])
        self.assertTrue(invalid["parse_errors"])
        self.assertFalse(invalid["mutation_attempted"])
        self.assertTrue(invalid["bytes_preserved"])

        unicode = next(
            row for row in results["cases"] if row["name"] == "non-ascii-byte-spans"
        )
        self.assertGreater(unicode["non_ascii_span_count"], 0)
        self.assertFalse(unicode["span_failures"])


if __name__ == "__main__":
    unittest.main()
