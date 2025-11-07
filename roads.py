# -*- coding: utf-8 -*-
"""
roads.py — Fetch road forecasts, warnings, works, and live sensor data.
-----------------------------------------------------------------------

Structure:
1) Imports
2) Configuration
3) Generic fetch helpers
4) Coordinate helpers
5) Forecast fetchers (geometry & forecasts)
6) Condition helpers
7) Summary / terminal test
8) Live data fetchers (weather, camera, TMS, warnings)
9) Main entry
"""

# ----------------------------
# 1) IMPORTS
# ----------------------------
import requests
from requests.exceptions import ReadTimeout, ConnectionError
from datetime import datetime
import time
import json
import os
import re
import math

# ----------------------------
# 2) CONFIGURATION
# ----------------------------
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")

def load_config():
    """Load shared configuration file."""
    if not os.path.exists(CONFIG_PATH):
        raise FileNotFoundError("⚠️ config.json not found.")
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

cfg = load_config()

BOUNDING_BOX = cfg["BOUNDING_BOX"]
X_MIN = BOUNDING_BOX["X_MIN"]
Y_MIN = BOUNDING_BOX["Y_MIN"]
X_MAX = BOUNDING_BOX["X_MAX"]
Y_MAX = BOUNDING_BOX["Y_MAX"]

ROADS_OF_INTEREST = set(cfg["ROADS_OF_INTEREST"])
TMS_STATIONS = cfg.get("TMS_STATIONS", [])
RWIS_STATIONS = cfg.get("RWIS_STATIONS", [])
CAMERA_STATIONS = cfg.get("CAMERA_STATIONS", [])
FUTURE_MINUTES = cfg.get("FUTURE_MINUTES", 180)

HEADERS = {"Digitraffic-User": cfg.get("USER_AGENT", "Birgir-ainola-dashboard/1.0")}

# ----------------------------
# 3) GENERIC FETCH HELPERS
# ----------------------------
def get_json(url, retries=2, timeout=6):
    """Safely fetch JSON with retry and graceful fallback on any HTTP error."""
    for attempt in range(retries + 1):
        try:
            r = requests.get(url, headers=HEADERS, timeout=timeout)
            if r.status_code == 404:
                return None
            r.raise_for_status()
            return r.json()
        except (ReadTimeout, ConnectionError):
            if attempt == retries:
                print(f"⚠️ Network error fetching {url}")
                return None
            time.sleep(0.5)
        except requests.exceptions.HTTPError as e:
            print(f"⚠️ HTTP {r.status_code} for {url}")
            return None
        except Exception as e:
            print(f"⚠️ Unexpected error for {url}: {e}")
            return None

# ----------------------------
# 4) COORDINATE HELPERS
# ----------------------------
def safe_coords(feature):
    geom = feature.get("geometry")
    if not geom or "coordinates" not in geom:
        return None, None
    coords = geom["coordinates"]
    if isinstance(coords[0], (int, float)):
        return coords[0], coords[1]
    elif isinstance(coords[0], list):
        return safe_coords({"geometry": {"coordinates": coords[0]}})
    return None, None

def inside_bbox(lon, lat):
    if lon is None or lat is None:
        return False
    return X_MIN <= lon <= X_MAX and Y_MIN <= lat <= Y_MAX

# ----------------------------
# 5) FORECAST FETCHERS
# ----------------------------
def fetch_road_geometry():
    url = (
        f"https://tie.digitraffic.fi/api/weather/v1/forecast-sections"
        f"?xMin={X_MIN}&yMin={Y_MIN}&xMax={X_MAX}&yMax={Y_MAX}"
    )
    data = get_json(url)
    if data is None:
        return []
    return data.get("forecastSections", [])

def fetch_road_forecasts():
    geo_url = (
        f"https://tie.digitraffic.fi/api/weather/v1/forecast-sections"
        f"?xMin={X_MIN}&yMin={Y_MIN}&xMax={X_MAX}&yMax={Y_MAX}"
    )
    geo_data = get_json(geo_url)
    geometry = geo_data.get("features", []) if geo_data else []

    forecast_url = (
        f"https://tie.digitraffic.fi/api/weather/v1/forecast-sections/forecasts"
        f"?xMin={X_MIN}&yMin={Y_MIN}&xMax={X_MAX}&yMax={Y_MAX}"
    )
    forecast_data = get_json(forecast_url)
    if forecast_data is None:
        return {}, geometry

    def first_valid_float(values):
        for value in values:
            if value is None:
                continue
            try:
                number = float(value)
            except (TypeError, ValueError):
                continue
            if math.isnan(number):
                continue
            return number
        return None

    forecasts = {}
    for section in forecast_data.get("forecastSections", []):
        sid = section.get("id")
        fc = section.get("forecasts", [])
        if not fc:
            continue
        current = fc[0]
        cond = (
            current.get("overallRoadCondition")
            or current.get("forecastConditionReason", {}).get("roadCondition")
            or "UNKNOWN"
        )

        reason = current.get("forecastConditionReason") or {}
        water_mm = first_valid_float(
            [
                current.get("waterLayerThickness"),
                current.get("waterOnRoad"),
                current.get("waterLayerThicknessLeft"),
                current.get("waterLayerThicknessRight"),
                reason.get("waterLayerThickness"),
                reason.get("waterOnRoad"),
            ]
        )
        snow_mm = first_valid_float(
            [
                current.get("snowLayerThickness"),
                current.get("snowOnRoad"),
                reason.get("snowLayerThickness"),
                reason.get("snowOnRoad"),
            ]
        )

        forecasts[sid] = {
            "cond": cond,
            "roadTemp": current.get("roadTemperature"),
            "airTemp": current.get("temperature"),
            "time": current.get("time"),
            "waterOnRoad": water_mm,
            "snowOnRoad": snow_mm,
        }
    return forecasts, geometry

# ----------------------------
# 6) CONDITION HELPERS
# ----------------------------
HAZARDOUS = ("ICY", "SLIPP", "FROST", "SNOW", "SLUSH", "POOR")

def is_hazard(cond):
    return bool(cond and any(h in cond.upper() for h in HAZARDOUS))

# ----------------------------
# 7) SUMMARY / TERMINAL TEST
# ----------------------------
def fetch_roads_summary():
    print("Checking road conditions and works in bounding box...\n")
    geometry = fetch_road_geometry()
    forecasts, _ = fetch_road_forecasts()

    print(f"🚧 Hazardous road conditions on {', '.join(map(str, ROADS_OF_INTEREST))}:")
    found = False
    for feat in geometry:
        props = feat.get("properties", {})
        road_no = props.get("roadNumber")
        if road_no in ROADS_OF_INTEREST:
            cond = forecasts.get(props.get("id"), {}).get("cond")
            temp = forecasts.get(props.get("id"), {}).get("roadTemp")
            if cond and is_hazard(cond):
                print(f"  • Road {road_no} — {props.get('description')} | {cond} | {temp}°C")
                found = True
    if not found:
        print("  ✅ No hazardous surface conditions.\n")

# ----------------------------
# 8) LIVE DATA FETCHERS
# ----------------------------
def fetch_weather_stations():
    """Return list of RWIS weather stations with live data."""
    data = get_json("https://tie.digitraffic.fi/api/weather/v1/stations")
    if not data:
        return []
    stations = []
    for feat in data.get("features", []):
        props = feat.get("properties", {})
        sid = props.get("id")
        if sid not in RWIS_STATIONS:
            continue
        lon, lat = safe_coords(feat)
        if not inside_bbox(lon, lat):
            continue

        live = get_json(f"https://tie.digitraffic.fi/api/weather/v1/stations/{sid}/data")
        if not live:
            continue

        vals = {s["name"]: s.get("value") for s in live.get("sensorValues", []) if "name" in s}
        desc = {s["name"]: s.get("sensorValueDescriptionEn") for s in live.get("sensorValues", [])}

        stations.append({
            "id": sid,
            "name": props.get("name", sid),
            "lat": lat,
            "lon": lon,
            "airTemp": vals.get("ILMA"),
            "roadTemp": vals.get("TIE_1") or vals.get("TIE_2"),
            "wind": vals.get("KESKITUULI"),
            "humidity": vals.get("ILMAN_KOSTEUS"),
            "precipitation": desc.get("SADE") or desc.get("VALLITSEVA_SÄÄ"),
            "roadCondition": desc.get("KELI_1") or desc.get("KELI_2"),
        })
    return stations

def fetch_camera_stations():
    """Return list of selected camera stations with image URLs."""
    data = get_json("https://tie.digitraffic.fi/api/weathercam/v1/stations")
    if not data:
        return []
    cams = []
    for feat in data.get("features", []):
        props = feat.get("properties", {})
        cid = props.get("id")
        if cid not in CAMERA_STATIONS:
            continue
        lon, lat = safe_coords(feat)
        if not inside_bbox(lon, lat):
            continue
        urls = [
            f"https://weathercam.digitraffic.fi/{p['id']}.jpg"
            for p in props.get("presets", [])
            if p.get("inCollection")
        ]
        cams.append({
            "id": cid,
            "name": props.get("name", cid),
            "lat": lat,
            "lon": lon,
            "images": urls,
        })
    return cams

def fetch_tms_stations():
    """Return list of TMS traffic stations with live speeds and volumes."""
    data = get_json("https://tie.digitraffic.fi/api/tms/v1/stations")
    if not data:
        return []
    tms = []
    for feat in data.get("features", []):
        props = feat.get("properties", {})
        tms_id = props.get("tmsNumber")
        if tms_id not in TMS_STATIONS:
            continue
        lon, lat = safe_coords(feat)
        if not inside_bbox(lon, lat):
            continue

        # ✅ Use the correct endpoint directly
        live = get_json(f"https://tie.digitraffic.fi/api/tms/v1/stations/{tms_id}/data")
        if not live:
            continue

        # Extract key sensor values
        values = {v.get("name", ""): v.get("value") for v in live.get("sensorValues", [])}
        # Match Finnish key patterns for consistency
        speed = next(
            (float(v) for k, v in values.items() if re.search(r"KESKINOPEUS", k, re.I)),
            None,
        )
        volume = next(
            (float(v) for k, v in values.items() if re.search(r"OHITUKSET", k, re.I)),
            None,
        )

        tms.append({
            "id": tms_id,
            "name": props.get("name", f"TMS {tms_id}"),
            "lat": lat,
            "lon": lon,
            "speed": speed,
            "volume": volume,
        })

    return tms

def fetch_warnings():
    """Fetch traffic warnings and roadworks within bounding box."""
    url = "https://tie.digitraffic.fi/api/traffic-message/v1/messages"
    data = get_json(url)
    if data is None:
        return []
    results = []
    for feature in data.get("features", []):
        lon, lat = safe_coords(feature)
        if not inside_bbox(lon, lat):
            continue
        props = feature.get("properties", {})
        s_type = props.get("situationType", "")
        s_id = props.get("situationId", "")
        anns = props.get("announcements", [])
        if not anns:
            continue
        ann = anns[0]
        loc_details = ann.get("locationDetails", {}).get("roadAddressLocation", {})
        primary = loc_details.get("primaryPoint", {})
        secondary = loc_details.get("secondaryPoint", {})
        primary_name = primary.get("alertCLocation", {}).get("name", "")
        secondary_name = secondary.get("alertCLocation", {}).get("name", "")
        muni1 = primary.get("municipality", "")
        muni2 = secondary.get("municipality", "")
        def fmt_time(ts):
            if not ts:
                return None
            try:
                dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                return dt.strftime("%d.%m.%Y")
            except Exception:
                return None
        tinfo = ann.get("timeAndDuration", {})
        start_str = fmt_time(tinfo.get("startTime"))
        end_str = fmt_time(tinfo.get("endTime"))
        restrict_text = "—"
        for phase in ann.get("roadWorkPhases", []):
            for r in phase.get("restrictions", []):
                if r.get("type") == "SPEED_LIMIT":
                    res = r.get("restriction", {})
                    qty = res.get("quantity")
                    unit = res.get("unit")
                    if qty and unit:
                        restrict_text = f"{qty} {unit}"
                        break
            if restrict_text != "—":
                break
        title_map = {
            "ROAD_WORK": "Road work",
            "WEIGHT_RESTRICTION": "Weight restriction",
            "TRAFFIC_ANNOUNCEMENT": "Traffic announcement",
        }
        title = title_map.get(s_type, s_type.replace("_", " ").title() or "Traffic event")
        if primary_name and secondary_name:
            location_text = f"{primary_name} in {muni1} and {secondary_name} in {muni2}"
        elif primary_name:
            location_text = f"{primary_name} in {muni1}"
        else:
            location_text = f"Unknown road in {muni1 or muni2}"
        results.append({
            "id": s_id,
            "type": title,
            "location": location_text,
            "start": start_str,
            "end": end_str,
            "restrictions": restrict_text,
            "sender": ann.get("sender", "Unknown sender"),
            "coordinates": (lon, lat),
        })
    return results

# ----------------------------
# 9) MAIN ENTRY
# ----------------------------
if __name__ == "__main__":
    fetch_roads_summary()
    print("\n📡 Checking live sensors...")
    weather = fetch_weather_stations()
    print(f"🌡 Weather stations: {len(weather)} found")
    cams = fetch_camera_stations()
    print(f"📷 Cameras: {len(cams)} found")
    tms = fetch_tms_stations()
    print(f"🚗 TMS stations: {len(tms)} found")
    warns = fetch_warnings()
    print(f"🚧 Warnings / Roadworks: {len(warns)} found")
