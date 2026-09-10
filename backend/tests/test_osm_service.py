"""Phase 6 OSM-layer tests — Overpass provider, GeoJSON normalization, cache,
retry/backoff and the /api/v1/osm endpoint. Retry/cache tests run against a
mocked transport; live Overpass hits are skip-gated on provider reachability.
"""

import asyncio
import unittest
from unittest import mock

import httpx

from app.services import osm_service
from app.services.osm_service import (
    OSMError,
    OSMInvalidRequest,
    build_feature_collection,
    parse_bbox,
)


class _NullSession:
    """DB stand-in that cannot reach PostGIS — proves graceful degrade."""

    async def execute(self, *a, **k):
        raise RuntimeError("database unavailable")

    async def commit(self):
        return None

    async def rollback(self):
        return None


class _OkResp:
    def __init__(self, payload, status_code=200):
        self.status_code = status_code
        self._payload = payload
        self.text = f"fake http {status_code}"

    def json(self):
        return self._payload


def _sample_elements(category="roads"):
    return [
        {"type": "node", "id": 1, "lat": 10.09, "lon": 77.05,
         "tags": {"amenity": "hospital", "name": "District Hospital"}},
        {"type": "way", "id": 2, "tags": {"highway": "primary", "name": "NH-49"},
         "geometry": [
             {"lat": 10.09, "lon": 77.05}, {"lat": 10.10, "lon": 77.06},
             {"lat": 10.11, "lon": 77.07}]},
        {"type": "way", "id": 3, "tags": {"building": "yes"},
         "geometry": [
             {"lat": 10.09, "lon": 77.05}, {"lat": 10.09, "lon": 77.06},
             {"lat": 10.10, "lon": 77.06}, {"lat": 10.10, "lon": 77.05},
             {"lat": 10.09, "lon": 77.05}]},
        {"type": "way", "id": 4, "tags": {"building": "yes"}},  # no geometry -> skipped
    ]


async def _noop_sleep(_s):
    return None


class OsmServiceTests(unittest.TestCase):
    def test_parse_bbox_valid(self):
        b = parse_bbox("76.8,9.9,77.3,10.4")
        self.assertEqual(b, (76.8, 9.9, 77.3, 10.4))

    def test_parse_bbox_rejects_invalid(self):
        for bad in [None, "", "1,2,3", "a,b,c,d", "0,91,1,92",
                    "77,10,76,11", "-181,0,-170,1"]:
            with self.assertRaises(OSMInvalidRequest, msg=bad):
                parse_bbox(bad)

    def test_parse_bbox_rejects_huge_area(self):
        with self.assertRaises(OSMInvalidRequest):
            parse_bbox("-1,-1,50,50")  # > 2 deg²

    def test_build_feature_collection_geometry_types(self):
        fc = build_feature_collection(_sample_elements(), "roads")
        self.assertEqual(fc["type"], "FeatureCollection")
        nodes = [f for f in fc["features"] if f["properties"]["osm_type"] == "node"]
        ways = [f for f in fc["features"] if f["properties"]["osm_type"] == "way"]
        self.assertEqual(len(nodes), 1)
        self.assertEqual(nodes[0]["geometry"]["type"], "Point")
        self.assertEqual(nodes[0]["properties"]["name"], "District Hospital")
        self.assertEqual(nodes[0]["properties"]["kind"], "hospital")
        self.assertEqual(len(ways), 2)
        self.assertEqual(ways[0]["geometry"]["type"], "LineString")
        self.assertEqual(ways[1]["geometry"]["type"], "Polygon")
        self.assertEqual(ways[1]["properties"]["kind"], "building")

    @mock.patch.object(osm_service, "_sleep", _noop_sleep)
    def test_query_overpass_retries_then_succeeds(self):
        calls = []

        class _FlakyClient:
            def __init__(self, *a, **k):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return False

            async def post(self, *a, **k):
                calls.append(1)
                if len(calls) < 3:
                    raise httpx.ConnectError("engine down")
                return _OkResp({"elements": _sample_elements()})

        with mock.patch.object(httpx, "AsyncClient", _FlakyClient):
            elements = asyncio.run(osm_service._query_overpass("..."))
        self.assertEqual(len(calls), 3)
        self.assertEqual(len(elements), 4)

    @mock.patch.object(osm_service, "_sleep", _noop_sleep)
    def test_query_overpass_gives_up_honestly(self):
        class _DeadClient:
            def __init__(self, *a, **k):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return False

            async def post(self, *a, **k):
                raise httpx.ConnectError("engine down")

        with mock.patch.object(httpx, "AsyncClient", _DeadClient):
            with self.assertRaises(OSMError):
                asyncio.run(osm_service._query_overpass("..."))

    def test_query_overpass_rejects_overpass_error_payload(self):
        class _ErrClient:
            def __init__(self, *a, **k):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return False

            async def post(self, *a, **k):
                return _OkResp({"remark": "runtime error: Query timed out"})

        with mock.patch.object(httpx, "AsyncClient", _ErrClient):
            with self.assertRaises(OSMError):
                asyncio.run(osm_service._query_overpass("..."))

    @mock.patch.object(osm_service, "_sleep", _noop_sleep)
    def test_get_osm_features_cache_and_provenance(self):
        class _OnceClient:
            post_calls = 0

            def __init__(self, *a, **k):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return False

            async def post(self, *a, **k):
                type(self).post_calls += 1
                return _OkResp({"elements": _sample_elements()})

        with mock.patch.object(httpx, "AsyncClient", _OnceClient):
            session = _NullSession()
            osm_service._OSM_CACHE.clear()
            bbox = (71.0, 8.0, 71.5, 8.5)  # unique sig — never cached by other tests
            first = asyncio.run(
                osm_service.get_osm_features(session, "roads", bbox)
            )
            second = asyncio.run(
                osm_service.get_osm_features(session, "roads", bbox)
            )
        self.assertEqual(first["data_status"], "LIVE")
        self.assertFalse(first["cache"])
        self.assertEqual(first["category"], "roads")
        self.assertEqual(second["data_status"], "CACHED")
        self.assertTrue(second["cache"])
        self.assertEqual(_OnceClient.post_calls, 1)
        # distinct bbox -> distinct cache key
        with mock.patch.object(httpx, "AsyncClient", _OnceClient):
            _OnceClient.post_calls = 0
            other = asyncio.run(
                osm_service.get_osm_features(_NullSession(), "roads", (76.0, 9.0, 76.5, 9.5))
            )
        self.assertEqual(_OnceClient.post_calls, 1)
        self.assertEqual(other["data_status"], "LIVE")

    def test_unknown_category_rejected(self):
        with self.assertRaises(OSMInvalidRequest):
            asyncio.run(
                osm_service.get_osm_features(_NullSession(), "nope", (76.0, 9.0, 76.5, 9.5))
            )


def _overpass_reachable() -> bool:
    try:
        r = httpx.get("https://overpass-api.de/api/status", timeout=10)
        return r.status_code == 200
    except Exception:
        return False


LIVE = unittest.skipUnless(_overpass_reachable(), "Overpass not reachable — skipping")


@LIVE
class LiveOverpassTests(unittest.TestCase):
    def test_live_road_layer_dukki_pilot(self):
        """Real end-to-end OSM fetch over the Idukki pilot box (skip-gated)."""
        bbox = (76.88, 9.90, 77.26, 10.31)
        payload = asyncio.run(
            osm_service.get_osm_features(_NullSession(), "roads", bbox)
        )
        self.assertEqual(payload["data_status"], "LIVE")
        features = payload["feature_collection"]["features"]
        self.assertGreater(payload["count"], 0, "expected real OSM roads in Idukki pilot")
        kinds = {f["properties"].get("kind") for f in features}
        self.assertTrue({"primary", "secondary", "service", "residential"} & kinds,
                        f"expected typical road kinds, got {sorted(kinds)[:8]}")
        for f in features[:3]:
            self.assertEqual(f["type"], "Feature")


if __name__ == "__main__":
    unittest.main()

# ── API-level tests: /api/v1/osm/* (FastAPI TestClient with mocked Overpass) ──

from fastapi.testclient import TestClient  # noqa: E402
from app.db.database import get_db  # noqa: E402
from app.main import app  # noqa: E402


class OsmApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app.dependency_overrides[get_db] = lambda: iter([_NullSession()])
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        app.dependency_overrides.pop(get_db, None)

    def setUp(self):
        osm_service._OSM_CACHE.clear()

    API_BBOX = "73.0,8.0,73.5,8.5"

    @mock.patch.object(osm_service, "_query_overpass", new_callable=mock.AsyncMock)
    def test_roads_returns_geojson(self, q):
        q.return_value = _sample_elements()
        r = self.client.get("/api/v1/osm/roads",
                            params={"bbox": self.API_BBOX})
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["type"], "FeatureCollection")
        self.assertEqual(body["data_status"], "LIVE")
        self.assertGreater(body["count"], 0)

    def test_bad_bbox_400(self):
        r = self.client.get("/api/v1/osm/roads", params={"bbox": "1,2,3"})
        self.assertEqual(r.status_code, 400)

    @mock.patch.object(osm_service, "_query_overpass", new_callable=mock.AsyncMock)
    def test_all_categories_geojson(self, q):
        q.side_effect = [_sample_elements()] * 4
        r = self.client.get("/api/v1/osm/features",
                            params={"bbox": "73.0,8.0,73.5,8.5"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["type"], "FeatureCollection")
        self.assertEqual(set(r.json()["categories"].keys()),
                         {"roads", "buildings", "facilities", "water"})

    @mock.patch.object(osm_service, "_query_overpass", new_callable=mock.AsyncMock)
    def test_provider_down_503(self, q):
        q.side_effect = OSMError("Overpass unreachable")
        r = self.client.get("/api/v1/osm/water",
                            params={"bbox": "73.0,8.0,73.5,8.5"})
        self.assertEqual(r.status_code, 503)

    def test_categories_and_status(self):
        r = self.client.get("/api/v1/osm/categories")
        self.assertEqual(r.status_code, 200)
        self.assertIn("roads", {c["key"] for c in r.json()["categories"]})
        s = self.client.get("/api/v1/osm/status")
        self.assertEqual(s.status_code, 200)
        self.assertIn("reachable", s.json())