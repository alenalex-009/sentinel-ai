"""CLI: poll the weather provider and write OBSERVED rows to PostGIS.

Run from backend/:
    python scripts/ingest_weather.py
    python scripts/ingest_weather.py --json

Exit code: 0 on OK, non-zero when the provider or DB is unavailable.
"""

import argparse
import json
import logging
import sys

from app.ingestion import weather_ingester


def main() -> int:
    parser = argparse.ArgumentParser(description="Poll WeatherAPI.com into PostGIS")
    parser.add_argument("--json", action="store_true", help="print raw JSON result")
    args = parser.parse_args()

    # Never log request URLs (they carry the API key query param).
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    if args.json:
        logging.basicConfig(level=logging.WARNING)
    else:
        logging.basicConfig(level=logging.INFO)

    result = weather_ingester.run_all()

    if args.json:
        print(json.dumps(result, indent=2, default=str))
    else:
        print(f"Weather ingest status: {result['status']}")
        if result.get("reason"):
            print(f"  reason: {result['reason']}")
        for s in result.get("stations", []):
            err = f"  ERROR: {s['error']}" if s.get("error") else ""
            print(
                f"  {s['station_id']:10s} obs={s['observations']:2d} "
                f"fc={s['forecasts']:2d} rain24h={s.get('rainfall_mm_24h')} "
                f"rain72h={s.get('rainfall_mm_72h')}{err}"
            )

    return 0 if result["status"] in ("OK", "PARTIAL") else 1


if __name__ == "__main__":
    sys.exit(main())