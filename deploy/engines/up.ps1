# Sentinel AI - routing engine stack launcher (OSRM / Valhalla / GraphHopper)
#
# Dataset pipeline (idempotent, safe to run repeatedly):
#   1. Geofabrik discontinued the standalone Kerala extract (2026). We download
#      today's official "southern zone" extract, clip it to the Kerala
#      administrative boundary (GADM polygon) with osmium, and keep the
#      Kerala-only PBF as data/osrm/kerala-latest.osm.pbf. The 531MB zone
#      extract is removed after a successful clip (re-downloaded on demand).
#   2. OSRM dataset built once (guarded, self-heals partial builds).
#   3. Valhalla builds tiles on first run only (tile hashes).
#   4. GraphHopper imports on first run only (persistent graph cache).
#
# A running container is NOT "READY" - run deploy/engines/smoke.py afterwards
# for real reachable/ready checks against the dataset.
#
# Usage:  powershell -ExecutionPolicy Bypass -File up.ps1
#         Requires Docker Desktop running and WSL2 backend available.

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

# Load optional .env overrides into the process env so both this script and
# `docker compose` (which reads .env itself) stay in sync.
if (Test-Path ".env") {
    Get-Content ".env" | ForEach-Object {
        if ($_ -match '^\s*([^#;=][^=]*)=(.*)$') {
            [Environment]::SetEnvironmentVariable($matches[1].Trim(), $matches[2].Trim(), "Process")
        }
    }
}

$pbfUrl = [Environment]::GetEnvironmentVariable("KERALA_PBF_URL", "Process")
if (-not $pbfUrl) {
    $pbfUrl = "https://download.geofabrik.de/asia/india/southern-zone-latest.osm.pbf"
}
$polyUrl = [Environment]::GetEnvironmentVariable("KERALA_BOUNDARY_URL", "Process")
if (-not $polyUrl) {
    $polyUrl = "https://geodata.ucdavis.edu/gadm/gadm4.1/json/gadm41_IND_1.json"
}

New-Item -ItemType Directory -Force -Path (Join-Path $root "data\osrm")  | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $root "data\zone")  | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $root "data\tmp")   | Out-Null

$zonePath = Join-Path $root "data\zone\southern-zone-latest.osm.pbf"
$pbfPath  = Join-Path $root "data\osrm\kerala-latest.osm.pbf"
$polyPath = Join-Path $root "data\osrm\kerala.geojson"
$osrmDone = Join-Path $root "data\osrm\kerala-latest.osrm.build-complete"

# Minimal OSM PBF sanity check: sane big-endian header_size + protobuf field 1
# (wiretype 2) opening the OSMHeader message, and a non-trivial file size.
function Test-ValidPbf([string]$path) {
    if (-not (Test-Path $path)) { return $false }
    $f = Get-Item $path
    if ($f.Length -lt 1024) { return $false }
    try {
        $fs = [System.IO.File]::OpenRead($path)
        try {
            $b = New-Object byte[] 5
            if ($fs.Read($b, 0, 5) -ne 5) { return $false }
        } finally {
            $fs.Close()
        }
    } catch {
        return $false
    }
    $hdr = ($b[0] -shl 24) -bor ($b[1] -shl 16) -bor ($b[2] -shl 8) -bor $b[3]
    if ($hdr -lt 4 -or $hdr -gt 1048576) { return $false }
    return $b[4] -eq 0x0A
}

function Get-Download([string]$url, [string]$dest) {
    $curl = Get-Command curl.exe -ErrorAction SilentlyContinue
    if ($curl) {
        & curl.exe -sS -L --fail -o $dest $url
        if ($LASTEXITCODE -ne 0) { throw "Download failed (curl exit $LASTEXITCODE): $url" }
    } else {
        Invoke-WebRequest -Uri $url -OutFile $dest -UseBasicParsing
        if (-not $?) { throw "Download failed: $url" }
    }
}

# GeoJSON must be BOM-less UTF-8 (osmium's JSON parser rejects a BOM) and start
# with '{'. A UTF-8 BOM is treated as INVALID so a BOM file self-heals on rerun.
function Test-ValidPoly([string]$path) {
    if (-not (Test-Path $path)) { return $false }
    try {
        $bytes = [System.IO.File]::ReadAllBytes($path)
    } catch {
        return $false
    }
    if ($bytes.Length -ge 3 -and $bytes[0] -eq 0xEF -and $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF) { return $false }
    return $bytes.Length -ge 1 -and $bytes[0] -eq 0x7B
}

# 1a. Kerala boundary polygon (GADM level-1) - fetched once, cached on disk.
if (-not (Test-ValidPoly $polyPath)) {
    Write-Host "[up] fetching Kerala boundary polygon (GADM) ..."
    $gadmJson = Join-Path $root "data\osrm\gadm41_IND_1.json"
    Get-Download $polyUrl $gadmJson
    try {
        $fc = Get-Content $gadmJson -Raw | ConvertFrom-Json
    } catch {
        Remove-Item $gadmJson -Force
        throw "Could not parse GADM boundary file ($polyUrl): $($_.Exception.Message)"
    }
    $kf = $fc.features | Where-Object { $_.properties.NAME_1 -eq "Kerala" } | Select-Object -First 1
    if (-not $kf) {
        Remove-Item $gadmJson -Force
        throw "Kerala feature not found in GADM boundary file - check KERALA_BOUNDARY_URL"
    }
    $kerala = @{
        type       = "Feature"
        properties = @{ name = "Kerala"; source = "GADM 4.1 (gadm41_IND_1)" }
        geometry   = $kf.geometry
    } | ConvertTo-Json -Depth 100
    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($polyPath, $kerala, $utf8NoBom)
    Remove-Item $gadmJson -Force
    Write-Host "[up] boundary polygon written: $polyPath"
}

# 1b. Kerala PBF - present? then done. Else clip from the zone extract
#     (download the zone on demand, remove it after a successful clip).
if (Test-ValidPbf $pbfPath) {
    Write-Host "[up] Kerala PBF present and valid: $pbfPath"
} else {
    if (-not (Test-ValidPbf $zonePath)) {
        if (Test-Path $zonePath) { Remove-Item $zonePath -Force }
        Write-Host "[up] downloading zone extract: $pbfUrl ..."
        Get-Download $pbfUrl $zonePath
        if (-not (Test-ValidPbf $zonePath)) {
            throw "Downloaded zone extract is not a valid OSM PBF - aborting (check KERALA_PBF_URL)"
        }
    }
    Write-Host "[up] clipping zone extract to Kerala (osmium) ..."
    docker compose --profile build run --rm osmium-clip
    if ($LASTEXITCODE -ne 0) { throw "osmium-clip failed (exit $LASTEXITCODE)" }
    if (-not (Test-ValidPbf $pbfPath)) {
        throw "Clipped Kerala PBF is not valid - aborting"
    }
    Remove-Item $zonePath -Force
    $bboxTmp = Join-Path $root "data\tmp\kerala-bbox.osm.pbf"
    if (Test-Path $bboxTmp) { Remove-Item $bboxTmp -Force }
    Write-Host "[up] Kerala PBF ready: $pbfPath (zone extract removed to save disk)"
}

# 2. OSRM dataset - build once (re-runs if a previous build was partial).
if (Test-ValidPbf $pbfPath) {
    if (-not (Test-Path $osrmDone)) {
        Write-Host "[up] clearing stale OSRM artifacts, then extract + partition + customize ..."
        Get-ChildItem (Join-Path $root "data\osrm") -Filter "kerala-latest.osrm*" -ErrorAction SilentlyContinue |
            Remove-Item -Force -ErrorAction SilentlyContinue
        docker compose --profile build run --rm osrm-build
        if ($LASTEXITCODE -ne 0) { throw "osrm-build failed (exit $LASTEXITCODE)" }
    } else {
        Write-Host "[up] OSRM dataset present - skipping build"
    }
} else {
    throw "Valid Kerala PBF not available at $pbfPath - cannot build OSRM dataset"
}

# 3. Validate the compose file, then start the runtime services.
Write-Host "[up] validating compose configuration ..."
docker compose config --quiet
if ($LASTEXITCODE -ne 0) { throw "docker compose config invalid" }

Write-Host "[up] starting osrm / valhalla / graphhopper ..."
docker compose up -d
if ($LASTEXITCODE -ne 0) { throw "docker compose up failed" }

docker compose ps
Write-Host ""
Write-Host "[up] stack started. Datasets under $root\data (persistent)."
Write-Host "[up] NOTE: containers running != engines READY. Run:"
Write-Host "      backend\.venv311\Scripts\python.exe deploy\engines\smoke.py"