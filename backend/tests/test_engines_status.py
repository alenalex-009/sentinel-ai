"""Task B1 — engines_status reachable/ready + policy helpers.

The ready path mocks httpx entirely (no network). The unreachable path also
mocks httpx (the client raises on transport), and the not-configured path
points the resolvers at None so no request is ever attempted.
"""

import unittest
from unittest.mock import AsyncMock, MagicMock, patch


class _FakeResponse:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


def _get_response(url: str) -> _FakeResponse:
    if "route/v1/driving" in url:  # OSRM probe + ready
        return _FakeResponse(200, {"code": "Ok", "routes": [{"distance": 1000}]})
    if url.endswith("/status"):    # Valhalla probe
        return _FakeResponse(200, {"version": "3.8.3", "available_actions": ["route"]})
    if "/info" in url:             # GraphHopper probe
        return _FakeResponse(200, {"version": "10.0", "profiles": [{"name": "car"}]})
    if "/route" in url:            # GraphHopper ready
        return _FakeResponse(200, {"paths": [{"distance": 1000, "time": 60}]})
    return _FakeResponse(404, {})


def _ready_client_patch():
    client = AsyncMock()
    client.get = AsyncMock(side_effect=_get_response)
    client.post = AsyncMock(
        side_effect=lambda url, json=None, **kw: _FakeResponse(200, {"trip": {"summary": {}}})
    )
    client.__aenter__.return_value = client
    factory = MagicMock(return_value=client)
    return patch("app.services.multi_engine_routing.httpx.AsyncClient", factory)


def _dead_host_client_patch():
    client = AsyncMock()
    async def _boom(*args, **kwargs):
        raise OSError("connection refused")
    client.get = AsyncMock(side_effect=_boom)
    client.post = AsyncMock(side_effect=_boom)
    client.__aenter__.return_value = client
    factory = MagicMock(return_value=client)
    return patch("app.services.multi_engine_routing.httpx.AsyncClient", factory)


_RECORD_IMPORT = "app.services.multi_engine_routing"


class EnginesStatusTests(unittest.IsolatedAsyncioTestCase):

    def _resolve(self):
        from app.services import multi_engine_routing as m
        return m

    async def test_not_configured_engines_are_honest(self):
        m = self._resolve()
        with patch(f"{_RECORD_IMPORT}.graphhopper_base_url", return_value=None), \
             patch(f"{_RECORD_IMPORT}._osrm_base_url", return_value=None), \
             patch(f"{_RECORD_IMPORT}._valhalla_base_url", return_value=None):
            status = await m.engines_status("kerala")
        self.assertEqual(status["region"], "kerala")
        self.assertIn("policy", status)
        self.assertEqual(set(status["engines"].keys()), {"graphhopper", "osrm", "valhalla"})
        for engine, entry in status["engines"].items():
            self.assertFalse(entry["reachable"])
            self.assertFalse(entry["ready"])
            self.assertFalse(entry["ok"])
            self.assertEqual(entry["detail"], "Not configured")
            self.assertIsNone(entry["url"])
            self.assertIn("role", entry)
        self.assertTrue(status["engines"]["graphhopper"]["experimental"])
        self.assertEqual(status["engines"]["osrm"]["role"], "primary")
        self.assertEqual(status["engines"]["valhalla"]["role"], "advanced")
        self.assertEqual(status["engines"]["graphhopper"]["role"], "optional")
        self.assertEqual(status["policy"]["ROUTE_STANDARD"], "osrm -> valhalla")
        self.assertEqual(status["policy"]["ROUTE_ADVANCED"], "valhalla -> none")
        self.assertEqual(status["policy"]["ROUTE_MATRIX"], "osrm -> valhalla")
        self.assertEqual(status["policy"]["OPTIMIZATION"], "ortools (greedy fallback)")

    async def test_unreachable_hosts_report_unreachable(self):
        m = self._resolve()
        with _dead_host_client_patch(), \
             patch(f"{_RECORD_IMPORT}.graphhopper_base_url", return_value="http://localhost:1"), \
             patch(f"{_RECORD_IMPORT}._osrm_base_url", return_value="http://localhost:2"), \
             patch(f"{_RECORD_IMPORT}._valhalla_base_url", return_value="http://localhost:3"):
            status = await m.engines_status("kerala")
        for entry in status["engines"].values():
            self.assertFalse(entry["reachable"])
            self.assertFalse(entry["ready"])
            self.assertFalse(entry["ok"])
            self.assertIn("Unreachable", entry["detail"])
        self.assertTrue(status["engines"]["graphhopper"]["experimental"])

    async def test_ready_path_with_all_engines_healthy(self):
        m = self._resolve()
        urls = {
            "osrm": "http://osrm:5000", "valhalla": "http://valhalla:8002",
            "graphhopper": "http://graphhopper:8989",
        }
        with _ready_client_patch(), \
             patch(f"{_RECORD_IMPORT}.graphhopper_base_url", return_value=urls["graphhopper"]), \
             patch(f"{_RECORD_IMPORT}._osrm_base_url", return_value=urls["osrm"]), \
             patch(f"{_RECORD_IMPORT}._valhalla_base_url", return_value=urls["valhalla"]):
            status = await m.engines_status("kerala")
        for engine, entry in status["engines"].items():
            self.assertTrue(entry["reachable"], engine)
            self.assertTrue(entry["ready"], engine)
            self.assertTrue(entry["ok"], engine)
            self.assertEqual(entry["url"], urls[engine])
            self.assertNotIn("Not configured", entry["detail"])
        self.assertTrue(status["engines"]["graphhopper"]["experimental"])


class PickEngineTests(unittest.IsolatedAsyncioTestCase):

    async def test_returns_first_ready_engine_in_chain(self):
        from app.services import multi_engine_routing as m
        urls = {
            "osrm": "http://osrm:5000", "valhalla": "http://valhalla:8002",
        }
        with _ready_client_patch(), \
             patch(f"{_RECORD_IMPORT}.graphhopper_base_url", return_value=None), \
             patch(f"{_RECORD_IMPORT}._osrm_base_url", return_value=urls["osrm"]), \
             patch(f"{_RECORD_IMPORT}._valhalla_base_url", return_value=urls["valhalla"]):
            self.assertEqual(await m.pick_engine("kerala", "ROUTE_STANDARD"), "osrm")
            self.assertEqual(await m.pick_engine("kerala", "ROUTE_MATRIX"), "osrm")
            self.assertEqual(await m.pick_engine("kerala", "ROUTE_ADVANCED"), "valhalla")

    async def test_returns_none_when_no_engine_ready(self):
        from app.services import multi_engine_routing as m
        with _dead_host_client_patch(), \
             patch(f"{_RECORD_IMPORT}.graphhopper_base_url", return_value=None), \
             patch(f"{_RECORD_IMPORT}._osrm_base_url", return_value="http://osrm:5000"), \
             patch(f"{_RECORD_IMPORT}._valhalla_base_url", return_value="http://valhalla:8002"):
            self.assertIsNone(await m.pick_engine("kerala", "ROUTE_STANDARD"))

    async def test_returns_none_for_unknown_or_unconfigured_policy(self):
        from app.services import multi_engine_routing as m
        self.assertIsNone(await m.pick_engine("kerala", "no-such-policy"))
        with patch(f"{_RECORD_IMPORT}.graphhopper_base_url", return_value=None), \
             patch(f"{_RECORD_IMPORT}._osrm_base_url", return_value=None), \
             patch(f"{_RECORD_IMPORT}._valhalla_base_url", return_value=None):
            self.assertIsNone(await m.pick_engine("kerala", "ROUTE_STANDARD"))


if __name__ == "__main__":
    unittest.main()