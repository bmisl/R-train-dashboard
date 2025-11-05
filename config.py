"""
=========================================
CONFIG.PY — CENTRAL SETTINGS FOR PROJECT
=========================================

This file is the SINGLE source of truth for:
✔ Geographic bounding box (map area of interest)
✔ Roads of interest for highlighting roadworks
✔ Train line settings (R-line), station names, and stop order
✔ Home station pair (origin → destination)
✔ Time window for fetching trains (past and future minutes)
✔ Station IDs for TMS / RWIS / Cameras inside bounding box

HOW IT WORKS:
-------------
1. When this file runs, it checks if config.json exists.
2. If config.json does NOT exist:
      → It scans Digitraffic APIs for TMS, RWIS, and Camera stations
      → Combines this with train + road settings
      → Saves everything into config.json
3. If config.json already exists:
      → Nothing is changed (fast startup)
4. Other scripts (main.py, roads.py, trains.py) simply load config.json.

Only change this file if:
✔ You move to another region
✔ You want a different train line or roads
✔ You want a different origin/destination station

"""

# ===============================
# 1. IMPORTS
# ===============================
import os
import json
import requests

# ===============================
# 2. CONFIGURATION FILE NAME
# ===============================
CONFIG_FILE = "config.json"

# ===============================
# 3. GEOGRAPHIC BOUNDING BOX
# ===============================
# Define the geographic area of interest for your commute.
# This bounding box determines which sensors, weather stations,
# roadworks, and cameras are shown or processed in all other scripts.
#
# Coordinates are in standard WGS84 format:
#   Longitude (X) = East–West direction
#   Latitude  (Y) = North–South direction
#
# ⚠️ IMPORTANT:
# - These must be numeric values (floats), not strings in quotation marks.
#   For example: 25.50 ✅   but  "25.50" ❌
# - Keeping them numeric ensures Python can compare coordinates
#   correctly when filtering API data.
#
# The bounding box roughly covers the Järvenpää – Tuusula – Kerava area.
BOUNDING_BOX = {
    "X_MIN": 24.80,   # Minimum longitude (west edge)
    "Y_MIN": 60.10,   # Minimum latitude  (south edge)
    "X_MAX": 25.50,   # Maximum longitude (east edge)
    "Y_MAX": 60.70    # Maximum latitude  (north edge)
}


# ===============================
# 4. ROADS OF INTEREST (HIGHLIGHT ONLY)
# ===============================
ROADS_OF_INTEREST = [
    4,      # Highway 4 (E75 - Tuusulanväylä / Lahdenväylä)
    140,    # Old Tuusulantie
    145,
    146,
    11609   # Rantatie (by Tuusula lake)
]

# ===============================
# 5. TRAIN CONFIGURATION
# ===============================
TRAIN_LINE = "R"   # Commuter line we care about

# Ordered list of R-train stops (south → north or Helsinki → Tampere)
TRAIN_STOPS = [
    "HKI",  # Helsinki
    "PSL",  # Pasila
    "TKL",  # Tikkurila
    "KE",   # Kerava
    "AIN",  # Ainola
    "JP",   # Järvenpää
    "SAU",  # Saunakallio
    "JK",   # Jokela
    "HY",   # Hyvinkää
    "RI",   # Riihimäki
    "TPE"   # Tampere
]

# Friendly station names
STATIONS = {
    "HKI": "Helsinki",
    "PSL": "Pasila",
    "TKL": "Tikkurila",
    "KE":  "Kerava",
    "AIN": "Ainola",
    "JP":  "Järvenpää",
    "SAU": "Saunakallio",
    "JK":  "Jokela",
    "HY":  "Hyvinkää",
    "RI":  "Riihimäki",
    "TPE": "Tampere"
}

# Define your default commute direction
HOME_STATIONS = {
    "origin": "AIN",     # Starting station
    "destination": "HKI" # End / target station
}

# ----------------------------
# 6. AINOLA + HOME MARKERS
# ----------------------------
AINOLA_COORDS = {
    "lat": 60.4553,
    "lon": 25.0984,
    "tooltip": "Ainola Parking"
}

HOME_COORDS = {
    "lat": 60.4446,
    "lon": 25.2428,
    "tooltip": "Close to home"
}

# ===============================
# 7. TRAIN TIME WINDOW (in minutes)
# ===============================
PAST_MINUTES = 0      # How many minutes in the past to include trains
FUTURE_MINUTES = 180  # How far into the future to show departures

# ===============================
# 8. HELPER FUNCTIONS FOR API & FILTERING
# ===============================

def inside_bbox(lon, lat):
    """Returns True if a coordinate is inside our bounding box."""
    return (
        BOUNDING_BOX["X_MIN"] <= lon <= BOUNDING_BOX["X_MAX"] and
        BOUNDING_BOX["Y_MIN"] <= lat <= BOUNDING_BOX["Y_MAX"]
    )

def fetch_json(url, timeout=10):
    """Safely fetch JSON data from a URL. Return None if failure occurs."""
    try:
        r = requests.get(url, timeout=timeout)
        r.raise_for_status()
        return r.json()
    except:
        return None

# -------------------------------
# 7A. Scan TMS traffic sensors
# -------------------------------
def scan_tms():
    url = "https://tie.digitraffic.fi/api/tms/v1/stations"
    data = fetch_json(url)
    ids = []
    if not data:
        return ids

    for feat in data.get("features", []):
        coords = feat.get("geometry", {}).get("coordinates", [])
        if len(coords) < 2:
            continue
        lon, lat = coords[0], coords[1]
        if inside_bbox(lon, lat):
            station_id = feat.get("properties", {}).get("id")
            if station_id is not None:
                ids.append(station_id)
    return ids

# -------------------------------
# 8B. Scan RWIS road weather stations
# -------------------------------
def scan_rwis():
    url = "https://tie.digitraffic.fi/api/weather/v1/stations"
    data = fetch_json(url)
    ids = []
    if not data:
        return ids

    for feat in data.get("features", []):
        coords = feat.get("geometry", {}).get("coordinates", [])
        if len(coords) < 2:
            continue
        lon, lat = coords[0], coords[1]
        if inside_bbox(lon, lat):
            station_id = feat.get("properties", {}).get("id")
            if station_id is not None:
                ids.append(station_id)
    return ids

# -------------------------------
# 8C. Scan Weather Cameras
# -------------------------------
def scan_cameras():
    url = "https://tie.digitraffic.fi/api/weathercam/v1/stations"
    data = fetch_json(url)
    ids = []
    if not data:
        return ids

    for feat in data.get("features", []):
        coords = feat.get("geometry", {}).get("coordinates", [])
        if len(coords) < 2:
            continue
        lon, lat = coords[0], coords[1]
        if inside_bbox(lon, lat):
            cam_id = feat.get("properties", {}).get("id") or feat.get("id")
            if cam_id:
                ids.append(cam_id)
    return ids

# ===============================
# 9. CREATE & SAVE CONFIG IF MISSING
# ===============================
def build_config():
    """Scans APIs + builds config.json with all required settings and marker coordinates."""
    print("🔍 Scanning Digitraffic stations inside bounding box...")

    tms_ids = scan_tms()
    rwis_ids = scan_rwis()
    cam_ids = scan_cameras()

    cfg = {
        # --- Core area and data sources ---
        "BOUNDING_BOX": BOUNDING_BOX,
        "ROADS_OF_INTEREST": ROADS_OF_INTEREST,
        "TMS_STATIONS": tms_ids,
        "RWIS_STATIONS": rwis_ids,
        "CAMERA_STATIONS": cam_ids,

        # --- Train / commute configuration ---
        "TRAIN_LINE": TRAIN_LINE,
        "TRAIN_STOPS": TRAIN_STOPS,
        "STATIONS": STATIONS,
        "HOME_STATIONS": HOME_STATIONS,
        "PAST_MINUTES": PAST_MINUTES,
        "FUTURE_MINUTES": FUTURE_MINUTES,

        # --- Fixed map markers (for display.py) ---
        "AINOLA_COORDS": AINOLA_COORDS,
        "HOME_COORDS": HOME_COORDS
    }

    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)

    print(f"✅ {CONFIG_FILE} created! ({len(tms_ids)} TMS, {len(rwis_ids)} RWIS, {len(cam_ids)} Cameras)")


# ===============================
# 10. PUBLIC FUNCTION TO ENSURE CONFIG EXISTS
# ===============================
def ensure_config():
    """Creates config.json if it doesn't exist yet."""
    if not os.path.exists(CONFIG_FILE):
        build_config()

# If this file is run directly: create config if needed
if __name__ == "__main__":
    ensure_config()
