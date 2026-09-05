#!/bin/bash
# Phase 5 — regional OSM extracts (Overpass API, genuine 2026-09-04 OSM data).
# Not committed; osm/*.osm are gitignored.
set -u
dl() {
  local name=$1 s=$2 w=$3 n=$4 e=$5 out=$6
  local q="[out:xml][timeout:900][maxsize:2000000000];(way[\"highway\"]($s,$w,$n,$e););(._;>;);out body;"
  echo "[$name] downloading bbox $s,$w,$n,$e -> $out  ($(date -u +%H:%M:%S))"
  curl -sS -m 1500 --data-urlencode "data=$q" https://overpass-api.de/api/interpreter -o "$out"
  local rc=$?
  local sz=$(stat -c%s "$out" 2>/dev/null || echo 0)
  echo "[$name] curl exit=$rc size=$sz ($(date -u +%H:%M:%S))"
  if [ "$rc" -ne 0 ] || [ "$sz" -lt 1000000 ]; then
    echo "[$name] FAILED — retrying via kumi mirror"
    curl -sS -m 1500 --data-urlencode "data=$q" https://overpass.kumi.systems/api/interpreter -o "$out"
    echo "[$name] retry exit=$? size=$(stat -c%s "$out" 2>/dev/null || echo 0)"
  fi
}
dl kerala 9.90 76.88 10.31 77.26 osm/kerala.osm
dl vizag 17.55 83.10 17.90 83.45 osm/vizag.osm
dl assam 26.05 91.60 26.30 91.95 osm/assam.osm
echo "ALL DOWNLOADS FINISHED $(date -u +%H:%M:%S)"
