# Sentinel AI — one-shot OSM XML → PBF converter.
# Base: the OSRM backend image (Debian-based, has apt + python3) because it is
# already pulled for osrm-prep; adds pyosmium for `osmium cat`-equivalent
# conversion. The upstream ghcr.io/osm-fr/osmium-tool image is pull-restricted
# (denied without auth), so this local build keeps the pipeline self-contained.
FROM ghcr.io/project-osrm/osrm-backend:latest

RUN apt-get update -qq \
    && apt-get install -y -qq --no-install-recommends python3 python3-pip \
    && rm -rf /var/lib/apt/lists/* \
    && (pip3 install --no-cache-dir --break-system-packages osmium \
        || pip3 install --no-cache-dir osmium)

# /data/osm holds the XML extract (mounted ro); /data/pbf receives the PBF.
# Any stale partial output from a previous crashed run is removed first.
COPY convert.py /usr/local/bin/convert.py
ENTRYPOINT ["python3", "/usr/local/bin/convert.py"]
