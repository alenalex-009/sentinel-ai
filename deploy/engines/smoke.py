"""Sentinel AI -- routing engine readiness smoke test.

Probes the local routing engines (OSRM :5000, Valhalla :8002, GraphHopper
:8989) with real requests and reports, per engine:

  reachable   cheap HTTP probe answered
  ready       a real Kerala routing request returned a valid payload

A running container is NOT ready (global constraint #2 from the Phase 7
spec). "ready" here means the engine answered a real routing request with a
valid payload, not that its process is up.

Exit code:
  0  all REQUIRED engines ready
  1  at least one REQUIRED engine not ready
  2  usage / internal error

Usage:
  python deploy/engines/smoke.py [--host HOST] [--require osrm,valhalla[,graphhopper]]

--require selects which engines must be ready for exit 0. Default:
osrm,valhalla (GraphHopper is optional/experimental and reported but not
required unless named). Pass --require "" to run without gates.

URL overrides (for CI / non-local deployments; ports still apply):
  OSRM_URL, VALHALLA_URL, GRAPHHOPPER_URL
"""

import json
import os
import sys
import time
import urllib.error
import urllib.request

DEFAULT_HOST = "localhost"

OSRM = {
    "name": "osrm",
    "base": "OSRM_URL",
    "probe": ("GET", "/route/v1/driving/76.93,10.01;77.16,10.03?overview=false", None),
    "probe_ok": lambda body, http: http == 200,
    "ready": ("GET", "/route/v1/driving/76.93,10.01;77.16,10.03?overview=false", None),
    "ready_ok": lambda body, http: http == 200 and bool(body.get("routes")),
}

VALHALLA = {
    "name": "valhalla",
    "base": "VALHALLA_URL",
    "probe": ("GET", "/status", None),
    "probe_ok": lambda body, http: http == 200 and bool(body.get("available_actions")),
    "ready": (
        "POST",
        "/route",
        {
            "locations": [
                {"lat": 10.01, "lon": 76.93},
                {"lat": 10.03, "lon": 77.16},
            ],
            "costing": "auto",
        },
    ),
    "ready_ok": lambda body, http: http == 200 and "trip" in body,
}

GRAPHHOPPER = {
    "name": "graphhopper",
    "base": "GRAPHHOPPER_URL",
    "probe": ("GET", "/info", None),
    "probe_ok": lambda body, http: http == 200 and bool(body.get("profiles")),
    "ready": ("GET", "/route?point=10.01,76.93&point=10.03,77.16&profile=car", None),
    "ready_ok": lambda body, http: http == 200 and isinstance(body.get("paths"), list) and len(body["paths"]) > 0,
}

ENGINES = {"osrm": OSRM, "valhalla": VALHALLA, "graphhopper": GRAPHHOPPER}
PORTS = {"osrm": 5000, "valhalla": 8002, "graphhopper": 8989}
ORDER = ["osrm", "valhalla", "graphhopper"]


def _base_url(engine, host):
    if os.environ.get(engine["base"]):
        return os.environ[engine["base"]].rstrip("/")
    return "http://{0}:{1}".format(host, PORTS[engine["name"]])


def request(method, url, payload=None, timeout=10.0):
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    started = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            latency = int((time.monotonic() - started) * 1000)
            try:
                return resp.status, json.loads(raw.decode("utf-8")), latency, None
            except ValueError:
                return resp.status, {}, latency, "non-JSON response"
    except urllib.error.HTTPError as exc:
        return exc.code, {}, int((time.monotonic() - started) * 1000), "HTTP {0}".format(exc.code)
    except Exception as exc:  # noqa: BLE001 - any transport failure => unreachable
        return None, {}, int((time.monotonic() - started) * 1000), str(exc) or type(exc).__name__


def probe_engine(engine, host):
    base = _base_url(engine, host)

    p_method, p_path, _p_payload = engine["probe"]
    http, body, latency, err = request(p_method, base + p_path)
    probe_ok = err is None and engine["probe_ok"](body, http)

    row = {
        "engine": engine["name"],
        "reachable": probe_ok,
        "ready": False,
        "latency_ms": latency,
        "detail": err if err else "HTTP {0}".format(http),
    }
    if not probe_ok:
        row["detail"] = "probe failed: {0}".format(row["detail"])
        return row

    row["detail"] = "probe ok"

    r_method, r_path, r_payload = engine["ready"]
    http, body, latency, err = request(r_method, base + r_path, r_payload)
    row["latency_ms"] = latency
    ready_ok = err is None and engine["ready_ok"](body, http)
    row["ready"] = ready_ok
    if ready_ok:
        row["detail"] = "probe ok / real route ok"
    else:
        row["detail"] = "probe ok / route failed: {0}".format(err if err else "invalid payload (HTTP {0})".format(http))
    return row


def main(argv):
    host = DEFAULT_HOST
    required = ["osrm", "valhalla"]
    idx = 0
    while idx < len(argv):
        arg = argv[idx]
        if arg == "--host":
            idx += 1
            host = argv[idx]
        elif arg == "--require":
            idx += 1
            parsed = argv[idx].strip()
            required = [] if parsed == "" else [e.strip() for e in parsed.split(",")]
        else:
            print("unknown argument: {0}".format(arg))
            print(__doc__)
            return 2
        idx += 1

    unknown = [e for e in required if e not in ENGINES]
    if unknown:
        print("unknown engine(s) in --require: {0}".format(", ".join(unknown)))
        return 2

    results = [probe_engine(ENGINES[name], host) for name in ORDER]
    header = "{0:<11} {1:<9} {2:<6} {3:<9} {4}".format(
        "engine", "reachable", "ready", "lat_ms", "detail"
    )
    print(header)
    print("-" * len(header))
    by_name = {}
    for row in results:
        by_name[row["engine"]] = row
        ms = row["latency_ms"]
        suffix = "  (experimental)" if row["engine"] == "graphhopper" else ""
        print(
            "{0:<11} {1:<9} {2:<6} {3:<9} {4}{5}".format(
                row["engine"],
                str(row["reachable"]).lower(),
                str(row["ready"]).lower(),
                ms if ms is not None else "-",
                row["detail"],
                suffix,
            )
        )

    failed = [name for name in required if not by_name[name]["ready"]]
    if failed:
        print("\nFAILED (required engines not ready): {0}".format(", ".join(failed)))
        return 1
    print("\nOK: all required engines ready ({0})".format(", ".join(required) if required else "none"))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))