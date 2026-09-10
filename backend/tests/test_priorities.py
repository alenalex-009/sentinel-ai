"""Task B3 — live-first district priorities (real scores, never invented).

DERIVED path uses a stub session returning fake risk_scores rows; the
DB-down path uses a session whose execute raises; empty-ledger path returns
the DEMO ranking with an explicit reason.
"""

import unittest

from fastapi.testclient import TestClient

from app.db.database import get_db
from app.main import app

_ROWS = [
    {"id": "munnar-central", "name": "Munnar Central", "population": 800,
     "current_score": 85.0},
    {"id": "rajakkad", "name": "Rajakkad", "population": 1500,
     "current_score": 78.0},
    {"id": "adimali", "name": "Adimali", "population": 600,
     "current_score": 42.0},
]


class FakeSession:
    def __init__(self, rows=None, fail=False):
        self.rows = rows or []
        self.fail = fail

    async def execute(self, sql, params=None):
        if self.fail:
            raise ConnectionError("db down")
        rows = self.rows

        class Mapping:
            def all(self):
                return list(rows)

        class Result:
            def mappings(self):
                return Mapping()

        return Result()


class DistrictPrioritiesServiceTests(unittest.IsolatedAsyncioTestCase):

    async def test_derived_ranking_orders_by_current_score_desc(self):
        from app.services import risk_service
        out = await risk_service.district_priorities(FakeSession(rows=_ROWS), "idukki")
        self.assertEqual(out["data_status"], "DERIVED")
        self.assertEqual(out["district_id"], "idukki")
        self.assertEqual(
            [h["habitation_id"] for h in out["habitations"]],
            ["munnar-central", "rajakkad", "adimali"],
        )
        top = out["habitations"][0]
        self.assertEqual(top["current_score"], 85.0)
        self.assertEqual(top["current_score_rounded"], 85)
        self.assertEqual(top["name"], "Munnar Central")
        self.assertIn("weights", out)
        self.assertAlmostEqual(out["weights"]["risk"], 0.35)

    async def test_db_down_returns_demo_with_reason(self):
        from app.services import risk_service
        out = await risk_service.district_priorities(FakeSession(fail=True), "idukki")
        self.assertEqual(out["data_status"], "DEMO")
        self.assertIn("query failed", out["reason"])
        self.assertGreater(len(out["habitations"]), 0, "demo ranking still returned")

    async def test_empty_ledger_returns_demo_with_reason(self):
        from app.services import risk_service
        out = await risk_service.district_priorities(FakeSession(rows=[]), "idukki")
        self.assertEqual(out["data_status"], "DEMO")
        self.assertIn("no live risk_scores", out["reason"])
        self.assertGreater(len(out["habitations"]), 0)


class DistrictPrioritiesApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app.dependency_overrides[get_db] = lambda: FakeSession(rows=_ROWS)
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        app.dependency_overrides.pop(get_db, None)

    def test_priorities_endpoint_derived(self):
        r = self.client.get("/api/v1/risk/priorities", params={"district_id": "idukki"})
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["data_status"], "DERIVED")
        self.assertEqual(body["habitations"][0]["habitation_id"], "munnar-central")

    def test_priorities_endpoint_db_down_is_demo(self):
        app.dependency_overrides[get_db] = lambda: FakeSession(fail=True)
        try:
            r = self.client.get("/api/v1/risk/priorities")
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.json()["data_status"], "DEMO")
            self.assertIn("reason", r.json())
        finally:
            app.dependency_overrides[get_db] = lambda: FakeSession(rows=_ROWS)


if __name__ == "__main__":
    unittest.main()