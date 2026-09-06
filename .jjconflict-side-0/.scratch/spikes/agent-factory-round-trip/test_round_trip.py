"""Automated checks for every required round-trip edit case."""

from __future__ import annotations

import unittest

from cases import CASES


class RoundTripCases(unittest.TestCase):
    """Require each evidence case to report a pass."""

    def test_required_cases(self) -> None:
        for case in CASES:
            with self.subTest(case=case.__name__):
                result = case(None)
                self.assertTrue(result["passed"], result)


if __name__ == "__main__":
    unittest.main()
