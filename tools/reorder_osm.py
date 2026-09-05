#!/usr/bin/env python3
"""Reorder an OSM XML extract so <node> elements precede <way> elements.

GraphHopper's OSM reader rejects files that place ways before the nodes they
reference ("OSM node elements must be located before way elements"). Overpass
output is not guaranteed to be grouped, so extracts fetched for routing should
be passed through this script once before import.

Usage:
    python tools/reorder_osm.py osm/vizag.osm          # rewrites in place
    python tools/reorder_osm.py osm/a.osm osm/b.osm    # src -> dst (in-place ok)

Element order after rewrite: meta/bounds tags first, then all <node>, then all
<way>, then all <relation>. Only the top-level element order changes — element
content is untouched.
"""

import os
import sys
import xml.etree.ElementTree as ET

TOP_LEVEL = ("node", "way", "relation")


def reorder(src: str, dst: str) -> int:
    tree = ET.parse(src)
    root = tree.getroot()
    bucket = {tag: [] for tag in TOP_LEVEL}
    other = []
    for el in list(root):
        (bucket[el.tag] if el.tag in bucket else other).append(el)
    for el in list(root):
        root.remove(el)
    for el in other + bucket["node"] + bucket["way"] + bucket["relation"]:
        root.append(el)
    tmp = dst + ".tmp"
    tree.write(tmp, encoding="UTF-8", xml_declaration=True)
    os.replace(tmp, dst)
    return len(bucket["node"]) + len(bucket["way"]) + len(bucket["relation"])


def main() -> None:
    if len(sys.argv) not in (2, 3):
        print(__doc__)
        sys.exit(2)
    src, dst = sys.argv[1], (sys.argv[2] if len(sys.argv) == 3 else sys.argv[1])
    total = reorder(src, dst)
    print(f"reordered {src} -> {dst} ({total} elements)")


if __name__ == "__main__":
    main()
