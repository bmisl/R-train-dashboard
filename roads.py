import requests
import streamlit as st

@st.cache_data(ttl=300)  # 300 seconds = 5 minutes
def get_road_data():
    return fetch_road_geometry(), fetch_road_forecasts(), fetch_warnings()

# ----------------------------
# CONSTANTS
# ----------------------------
HEADERS = {"Digitraffic-User": "Birgir-ainola-dashboard/1.0"}

# Ainola region bounding box (longitude, latitude)
X_MIN, Y_MIN = 25.00, 60.40
X_MAX, Y_MAX = 25.30, 60.55

# Roads we care about
INTEREST_ROADS = {146, 140, 145}

# Hazardous road surface terms
HAZARDOUS = ("ICY", "SLIPP", "FROST", "SNOW", "SLUSH", "POOR")

# ----------------------------
# Generic helper to fetch JSON
# ----------------------------
def get_json(url):
    r = requests.get(url, headers=HEADERS, timeout=20)
    r.raise_for_status()
    return r.json()

# ----------------------------
# Road geometry / structures
# ----------------------------
def fetch_road_geometry():
    url = (
        f"https://tie.digitraffic.fi/api/weather/v1/forecast-sections"
        f"?xMin={X_MIN}&yMin={Y_MIN}&xMax={X_MAX}&yMax={Y_MAX}"
    )
    data = get_json(url)
    return data.get("features", data.get("forecastSections", []))

def fetch_road_forecasts():
    url = (
        f"https://tie.digitraffic.fi/api/weather/v1/forecast-sections/forecasts"
        f"?xMin={X_MIN}&yMin={Y_MIN}&xMax={X_MAX}&yMax={Y_MAX}"
    )
    data = get_json(url)
    out = {}
    for s in data.get("forecastSections", []):
        sid = s.get("id")
        fc = s.get("forecasts", [])
        current = next((f for f in fc if f.get("type") == "OBSERVATION"), fc[0] if fc else None)
        if not current:
            continue
        cond = current.get("overallRoadCondition") or \
               current.get("forecastConditionReason", {}).get("roadCondition") or "UNKNOWN"
        out[sid] = {
            "cond": cond,
            "roadTemp": current.get("roadTemperature"),
            "airTemp": current.get("temperature"),
            "time": current.get("time")
        }
    return out

# ----------------------------
# Hazard detection for roads
# ----------------------------
def is_hazard(cond):
    if not cond:
        return False
    return any(h in cond.upper() for h in HAZARDOUS)

def color_for_condition(cond):
    if not cond:
        return "blue"
    c = cond.upper()
    if any(h in c for h in HAZARDOUS):
        return "red"
    if "WET" in c or "MOIST" in c:
        return "orange"
    return "blue"

# ----------------------------
# Safely extract a (lon, lat) from any GeoJSON coords format
# ----------------------------
def extract_lon_lat(coords):
    """
    Handles formats:
    - [lon, lat]
    - [[lon, lat], ...]
    - [[[lon, lat]]]
    Returns (lon, lat) as floats, or (None, None).
    """
    if not coords:
        return None, None

    # Case 1: [lon, lat]
    if isinstance(coords, list) and len(coords) >= 2:
        if isinstance(coords[0], (int, float)) and isinstance(coords[1], (int, float)):
            return coords[0], coords[1]

    # Case 2: [[lon, lat], ...]
    if isinstance(coords, list) and isinstance(coords[0], list):
        return extract_lon_lat(coords[0])

    return None, None

# ----------------------------
# Traffic warnings (filtered to bounding box)
# ----------------------------
def fetch_warnings():
    url = "https://tie.digitraffic.fi/api/traffic-message/v1/messages"
    data = get_json(url)
    out = []

    for feature in data.get("features", []):
        props = feature.get("properties", {})
        geom = feature.get("geometry", {})

        coords = geom.get("coordinates", None)
        lon, lat = extract_lon_lat(coords)

        if lon is None or lat is None:
            continue

        # Keep only warnings in Ainola/Helsinki region
        if X_MIN <= lon <= X_MAX and Y_MIN <= lat <= Y_MAX:
            out.append({"props": props, "lon": lon, "lat": lat})
    return out

# ----------------------------
# Optional CLI test
# ----------------------------
if __name__ == "__main__":
    print("Checking road conditions around Ainola...\n")

    try:
        geometry = fetch_road_geometry()
        forecasts = fetch_road_forecasts()

        # Hazardous surface check
        print("🚧 Hazardous road conditions on 140 / 145 / 146:")
        found = False
        for feat in geometry:
            props = feat.get("properties", {})
            if props.get("roadNumber") in INTEREST_ROADS:
                cond = forecasts.get(props.get("id"), {}).get("cond")
                temp = forecasts.get(props.get("id"), {}).get("roadTemp")
                if cond and is_hazard(cond):
                    print(f"  • Road {props.get('roadNumber')} — {props.get('description')} | {cond} | {temp}°C")
                    found = True
        if not found:
            print("  ✅ No hazardous surface conditions.\n")

        # Traffic warnings
        print("⚠ Traffic warnings nearby:")
        warns = fetch_warnings()

        # Split into two groups
        roadworks = []
        other_warnings = []

        for w in warns:
            props = w.get("props", {})
            if props.get("situationType") == "ROAD_WORK":
                roadworks.append(w)
            else:
                other_warnings.append(w)

        # Print non-roadwork warnings
        if other_warnings:
            for w in other_warnings:
                props = w.get("props", {})
                print(f"  • {props.get('situationType')} — {props.get('title', '(no title)')}")
        else:
            print("  ✅ No other traffic warnings in this area.")

        from datetime import datetime

        print("\n👷 Roadworks near Ainola:")
        if roadworks:
            for r in roadworks:
                props = r.get("props", {})
                ann = props.get("announcements", [{}])[0]

                # Extract road name + municipality from nested structure
                primary_point = ann.get("locationDetails", {}) \
                                .get("roadAddressLocation", {}) \
                                .get("primaryPoint", {})

                road_name = primary_point.get("roadName", "Unknown road")
                municipality = primary_point.get("municipality", "Unknown location")

                # releaseTime used as start time
                release_time = props.get("releaseTime", None)
                if release_time:
                    try:
                        dt = datetime.fromisoformat(release_time.replace("Z", "+00:00"))
                        start_str = dt.strftime("%d %B %Y")   # e.g. "22 September 2025"
                    except:
                        start_str = release_time
                else:
                    start_str = "Unknown start"

                print(f"  • Road: {road_name} in {municipality}")
                print(f"    🕒 start: {start_str}")
        else:
            print("  ✅ No active roadworks reported in this area.")

    except Exception as e:
        print(f"\n❌ Error: {e}")
