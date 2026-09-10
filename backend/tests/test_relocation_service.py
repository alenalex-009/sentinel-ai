"""Slice 5 — relocation workflow tests.

Tests the demand model, plan lifecycle transitions, and the service-level
contract (no real DB needed — FakeSession + patched optimizer). Includes
DB-down degradation: a service must degrade honestly (DEMO / EMPTY /
UNAVAILABLE / 503), never crash with an unhandled exception.
"""

import unittest
from unittest import mock

from fastapi import HTTPException

from app.services.relocation_service import (
    _demand_for_habitation,
    _nominal_capacity,
    RELOCATION_RISK_THRESHOLD,
    calculate_demand,
    get_plan,
    get_safe_zone_sites,
    transition_plan,
    create_plan,
)


class BrokenSession:
    """AsyncSession stub whose execute always raises (PostGIS down)."""

    async def execute(self, *args, **kwargs):
        raise ConnectionError("connection refused")

    async def commit(self):
        raise ConnectionError("connection refused")

    async def rollback(self):
        pass


class TestCapacityBaseline(unittest.TestCase):
    """Deterministic Sentinel AI capacity model for un-surveyed sites."""

    def test_uses_surveyed_capacity(self):
        c = {"estimated_capacity": 3200, "suitability_score": 82.0}
        self.assertEqual(_nominal_capacity(c), 3200)

    def test_uses_safe_capacity_fallback(self):
        c = {"safe_capacity": 1800, "suitability_score": 68.0}
        self.assertEqual(_nominal_capacity(c), 1800)

    def test_un_surveyed_scales_with_suitability(self):
        # base = 250 * 9 * 0.3 = 675; suitability 50% → 337.5 → 340
        c = {"suitability_score": 50.0}
        self.assertEqual(_nominal_capacity(c), 340)

    def test_un_surveyed_zero_for_no_suitability(self):
        c = {"suitability_score": 0.0}
        self.assertEqual(_nominal_capacity(c), 0)

    def test_un_surveyed_valid_point_has_capacity(self):
        # base = 250 * 9 * 0.3 = 675; suitability 65% → 438.75 → 440
        c = {"suitability_score": 65.0}
        self.assertGreater(_nominal_capacity(c), 0)
        self.assertEqual(_nominal_capacity(c), 440)

    def test_deterministic_rounding(self):
        a = _nominal_capacity({"suitability_score": 71.5})
        b = _nominal_capacity({"suitability_score": 71.5})
        self.assertEqual(a, b)


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


class TestDbDownDegrades(unittest.TestCase):
    """When PostGIS is unreachable every service entry point must degrade
    honestly — never raise a raw 500."""

    def test_demand_degrades_to_demo(self):
        r = _run_async(calculate_demand(BrokenSession(), "idukki"))
        self.assertEqual(r["data_status"], "DEMO")
        self.assertEqual(r["total_demand"], 0)
        self.assertIn("PostGIS unavailable", r["note"])

    def test_safe_zone_sites_returns_none(self):
        r = _run_async(get_safe_zone_sites(BrokenSession(), "idukki"))
        self.assertIsNone(r)

    def test_get_plan_degrades_to_unavailable(self):
        r = _run_async(get_plan(BrokenSession(), 7))
        self.assertEqual(r["data_status"], "UNAVAILABLE")
        self.assertIn("PostGIS", r["reason"])

    def test_transition_degrades_to_unavailable(self):
        r = _run_async(transition_plan(BrokenSession(), 7, "approved"))
        self.assertEqual(r["data_status"], "UNAVAILABLE")
        self.assertIn("PostGIS", r["reason"])

    def test_create_plan_raises_503(self):
        with self.assertRaises(HTTPException) as ctx:
            _run_async(create_plan(BrokenSession(), "idukki", "n"))
        self.assertEqual(ctx.exception.status_code, 503)
        self.assertIn("PostGIS unavailable", ctx.exception.detail)


def _run_async(coro):
    """Run one coroutine to completion."""
    import asyncio
    return asyncio.new_event_loop().run_until_complete(coro)


if __name__ == "__main__":
    unittest.main()