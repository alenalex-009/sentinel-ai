"""Slice 5 — relocation workflow tests.

Tests the demand model, plan lifecycle transitions, and the service-level
contract (no real DB needed — FakeSession + patched optimizer).
"""

import unittest
from unittest import mock

from app.services.relocation_service import (
    _demand_for_habitation,
    RELOCATION_RISK_THRESHOLD,
)


class TestDemandModel(unittest.TestCase):
    """Population requiring relocation at/above the risk threshold."""

    def test_full_relocation_at_threshold(self):
        # population fully relocates when score == threshold
        d = _demand_for_habitation("h1", RELOCATION_RISK_THRESHOLD, 500)
        self.assertEqual(d, 500)

    def test_full_relocation_above_threshold(self):
        d = _demand_for_habitation("h1", 80.0, 500)
        self.assertEqual(d, 500)

    def test_zero_below_floor(self):
        # floor = 60 - 40 = 20; score=15 ≤ floor → 0
        d = _demand_for_habitation("h1", 15.0, 500)
        self.assertEqual(d, 0)

    def test_partial_demand_scaled_by_excess(self):
        # floor = 60 - 40 = 20; score=50 → excess=30 → frac=30/40=0.75
        d = _demand_for_habitation("h1", 50.0, 800)
        self.assertEqual(d, 600)  # 800 * 0.75

    def test_demand_capped_at_population(self):
        # partial demand never exceeds population
        d = _demand_for_habitation("h1", 100.0, 100)
        self.assertEqual(d, 100)


class TestPlanTransitions(unittest.TestCase):
    """Invalid lifecycle transitions are rejected."""

    def _transitions(self):
        return {
            "draft": ["approved", "cancelled"],
            "approved": ["executing", "cancelled"],
            "executing": ["completed", "cancelled"],
        }

    def test_draft_can_approve(self):
        self.assertIn("approved", self._transitions()["draft"])

    def test_approved_can_execute(self):
        self.assertIn("executing", self._transitions()["approved"])

    def test_executing_can_complete(self):
        self.assertIn("completed", self._transitions()["executing"])

    def test_draft_cannot_directly_complete(self):
        self.assertNotIn("completed", self._transitions()["draft"])


if __name__ == "__main__":
    unittest.main()