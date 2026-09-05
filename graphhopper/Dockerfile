# GraphHopper 8.0 — self-hosted routing service (Phase 4)
# Uses the official graphhopper-web jar from Maven Central, pinned to 8.0.
# OSM road data is mounted read-only at /data/munnar.osm; the prepared graph
# cache lives in a named volume at /data/cache (see docker-compose.yml).
FROM eclipse-temurin:21-jre

WORKDIR /gh

COPY graphhopper-web-8.0.jar /gh/graphhopper-web.jar

EXPOSE 8989 8990

# config.yml is bind-mounted (editable without rebuild)
ENTRYPOINT ["java", "-Xmx2g", "-Xms256m", "-jar", "/gh/graphhopper-web.jar", "server", "/gh/config.yml"]
