"""USGS earthquake catalog ingestion → PostGIS (earthquake_events).

Reads the USGS CSV format (time,latitude,longitude,depth,mag,magType,nst,
gap,dmin,rms,net,id,updated,place,type,horizontalError,depthError,magError,
magNst,status,locationSource,magSource). Raw USGS fields are preserved as-is;
`geom` is the authoritative point geometry.

Historical context only — NEVER a prediction source. No deterministic
earthquake forecasting is claimed anywhere in Sentinel AI.

Idempotent: upsert on usgs_id (PK). Safe to re-run on the same file.
"""

import csv
import io
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

import psycopg2
import psycopg2.extras

from app.core.config import settings

_COLS = (
    "usgs_id", "occurred_at", "magnitude", "mag_type", "depth_km", "place",
    "latitude", "longitude", "geom", "nst", "gap", "dmin", "rms",
    "horizontal_error", "depth_error", "mag_error", "mag_nst", "status",
    "location_source", "mag_source", "reviewed", "source", "data_type",
    "data_status", "updated_at",
)


class EarthquakeParseError(Exception):
    pass


def _parse_time(value: str) -> Optional[datetime]:
    """USGS CSV time: '2000-07-29T17:50:03.510Z' → aware datetime."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _parse_float(value: str) -> Optional[float]:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _parse_int(value: str) -> Optional[int]:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except ValueError:
        return None


def parse_row(raw: dict) -> Optional[tuple]:
    """Normalize one USGS CSV row → DB tuple, or None if unusable.

    Skips non-earthquake rows (type != earthquake) and rows lacking required
    identity/time/coords (they cannot be placed in space or time).
    """
    if raw.get("type") not in (None, "", "earthquake"):
        return None
    occurred = _parse_time(raw.get("time") or "")
    lat = _parse_float(raw.get("latitude") or "")
    lon = _parse_float(raw.get("longitude") or "")
    usgs_id = (raw.get("id") or "").strip()
    if occurred is None or lat is None or lon is None or not usgs_id:
        return None

    status_raw = (raw.get("status") or "").strip().lower()
    reviewed = status_raw in ("reviewed", "automatic_ok") if status_raw else None

    return (
        usgs_id,
        occurred,
        _parse_float(raw.get("mag") or ""),
        (raw.get("magType") or "").strip() or None,
        _parse_float(raw.get("depth") or ""),
        (raw.get("place") or "").strip() or None,
        lat,
        lon,
        f"SRID=4326;POINT({lon:.6f} {lat:.6f})",
        _parse_int(raw.get("nst") or ""),
        _parse_float(raw.get("gap") or ""),
        _parse_float(raw.get("dmin") or ""),
        _parse_float(raw.get("rms") or ""),
        _parse_float(raw.get("horizontalError") or ""),
        _parse_float(raw.get("depthError") or ""),
        _parse_float(raw.get("magError") or ""),
        _parse_int(raw.get("magNst") or ""),
        (raw.get("status") or "").strip() or None,
        (raw.get("locationSource") or "").strip() or None,
        (raw.get("magSource") or "").strip() or None,
        reviewed,
        "usgs",
        "OBSERVED",
        "OBSERVED",
        _parse_time(raw.get("updated") or ""),
    )


def parse_file(path: str) -> List[tuple]:
    """Parse a USGS CSV into normalized rows, skipping unusable/duplicate ids."""
    with open(path, newline="", encoding="utf-8-sig") as f:
        return _parse_reader(f)


def parse_file_from_text(text: str) -> List[tuple]:
    """Parse USGS CSV content given as a string (test/CLI convenience)."""
    return _parse_reader(io.StringIO(text))


def _parse_reader(stream) -> List[tuple]:
    rows: List[tuple] = []
    seen: set[str] = set()
    reader = csv.DictReader(stream)
    for raw in reader:
        row = parse_row(raw)
        if row is None:
            continue
        if row[0] in seen:
            continue
        seen.add(row[0])
        rows.append(row)
    return rows


def ingest(path: str = "") -> dict:
    """Ingest a USGS CSV into PostGIS. Idempotent on usgs_id."""
    csv_path = (path or settings.EARTHQUAKE_CSV_PATH or "").strip()
    if not csv_path:
        return {
            "status": "UNAVAILABLE",
            "reason": "EARTHQUAKE_CSV_PATH not configured (server-side)",
            "rows_read": 0,
            "rows_inserted": 0,
            "rows_failed": 0,
            "source_path": None,
        }
    if not Path(csv_path).is_file():
        return {
            "status": "UNAVAILABLE",
            "reason": f"CSV not found: {csv_path}",
            "rows_read": 0,
            "rows_inserted": 0,
            "rows_failed": 0,
            "source_path": csv_path,
        }

    rows = parse_file(csv_path)
    if not rows:
        return {
            "status": "ERROR",
            "reason": "no usable rows parsed from CSV",
            "rows_read": 0,
            "rows_inserted": 0,
            "rows_failed": 0,
            "source_path": csv_path,
        }

    conn = psycopg2.connect(settings.DATABASE_URL, connect_timeout=5)
    inserted = 0
    failed = 0
    try:
        with conn.cursor() as cur:
            for row in rows:
                try:
                    cur.execute(
                        f"""
                        INSERT INTO earthquake_events ({", ".join(_COLS)})
                        VALUES %s
                        ON CONFLICT (usgs_id) DO UPDATE SET
                            occurred_at = EXCLUDED.occurred_at,
                            magnitude  = EXCLUDED.magnitude,
                            depth_km   = EXCLUDED.depth_km,
                            place      = EXCLUDED.place,
                            geom       = EXCLUDED.geom,
                            status     = EXCLUDED.status,
                            reviewed   = EXCLUDED.reviewed,
                            updated_at = EXCLUDED.updated_at,
                            ingested_at = NOW()
                        """,
                        (row,),
                    )
                    inserted += 1
                except Exception as exc:
                    failed += 1
                    # log first failure detail only; continue
        conn.commit()
    finally:
        conn.close()

    return {
        "status": "OK" if failed == 0 else "PARTIAL",
        "reason": f"{failed} rows failed" if failed else None,
        "rows_read": len(rows),
        "rows_inserted": inserted,
        "rows_failed": failed,
        "source_path": csv_path,
    }


if __name__ == "__main__":
    import json
    import sys
    result = ingest()
    print(json.dumps(result, indent=2))
    sys.exit(0 if result["status"] in ("OK", "PARTIAL") else 1)