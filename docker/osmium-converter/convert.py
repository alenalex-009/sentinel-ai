"""Sentinel AI — convert an OSM XML extract to PBF using pyosmium.

Runs inside the osm-convert one-shot container. Inputs/outputs (docker mounts):
  /data/osm/kerala.osm   — Overpass XML extract (read-only mount)
  /data/pbf/             — named volume; kerala.osm.pbf is (re)written here
"""

import os

import osmium

SRC = "/data/osm/kerala.osm"
DST = "/data/pbf/kerala.osm.pbf"


def main() -> None:
    if not os.path.exists(SRC):
        raise SystemExit(f"input missing: {SRC}")
    os.makedirs(os.path.dirname(DST), exist_ok=True)

    # A previous crashed run can leave a zero-byte file; pyosmium refuses to
    # overwrite an existing path, so remove it up front.
    if os.path.exists(DST):
        os.remove(DST)
        print(f"removed stale output: {DST}")

    writer = osmium.SimpleWriter(DST)
    copied = 0
    for obj in osmium.FileProcessor(SRC):
        writer.add(obj)
        copied += 1
    writer.close()

    size_mb = os.path.getsize(DST) / (1024 * 1024)
    print(f"converted {copied} OSM objects -> {DST} ({size_mb:.1f} MB)")


if __name__ == "__main__":
    main()
