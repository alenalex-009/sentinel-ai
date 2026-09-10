"""CLI: ingest the USGS India earthquake CSV into PostGIS.

Run from backend/:
    python scripts/ingest_earthquakes.py                     # uses settings.EARTHQUAKE_CSV_PATH
    python scripts/ingest_earthquakes.py "path/to/data.csv"  # explicit CSV

Idempotent (upsert on usgs_id). Exit 0 on OK/PARTIAL, non-zero on failure.
"""

import argparse
import json
import sys

from app.ingestion import earthquake_ingester


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Ingest USGS earthquake CSV into PostGIS (idempotent)"
    )
    parser.add_argument("path", nargs="?", default=None, help="CSV path (default: settings.EARTHQUAKE_CSV_PATH)")
    parser.add_argument("--json", action="store_true", help="print raw JSON result")
    args = parser.parse_args()

    result = earthquake_ingester.ingest(args.path)
    print(json.dumps(result, indent=2))
    return 0 if result["status"] in ("OK", "PARTIAL") else 1


if __name__ == "__main__":
    sys.exit(main())