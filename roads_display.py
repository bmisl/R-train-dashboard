"""
roads_display.py
----------------
Generates an interactive map showing:
- Road condition forecasts (colored by severity)
- Roadworks & warnings
- Weather, camera, and TMS data
- Home and Ainola markers
- Bounding box and legend

Uses data from roads.py and config.json.
"""

import folium
from folium.plugins import MiniMap
from folium import FeatureGroup, LayerControl
from datetime import datetime

from roads import (
    load_config,
    fetch_road_forecasts,
    fetch_warnings,
    fetch_weather_stations,
    fetch_camera_stations,
    fetch_tms_stations,
)

# ----------------------------
# 1) LOAD CONFIGURATION
# ----------------------------
cfg = load_config()
BOUNDING_BOX = cfg.get("BOUNDING_BOX", {})
ROADS_OF_INTEREST = cfg.get("ROADS_OF_INTEREST", [])

# Provide fallback coordinates if not in config.json
AINOLA = cfg.get("AINOLA_COORDS", {"lat": 60.475, "lon": 25.085, "tooltip": "Ainola Parking"})
HOME = cfg.get("HOME_COORDS", {"lat": 60.307, "lon": 25.038, "tooltip": "Home"})

X_MIN = BOUNDING_BOX["X_MIN"]
X_MAX = BOUNDING_BOX["X_MAX"]
Y_MIN = BOUNDING_BOX["Y_MIN"]
Y_MAX = BOUNDING_BOX["Y_MAX"]

center_lat = (Y_MIN + Y_MAX) / 2
center_lon = (X_MIN + X_MAX) / 2

# ----------------------------
# 2) COLOR CLASSIFICATION
# ----------------------------
def classify_condition(cond_text: str) -> str:
    if not cond_text:
        return "NORMAL"
    cond_text = cond_text.upper()
    if any(k in cond_text for k in ["ICE", "IC", "FROST", "SNOW", "SLUSH", "POOR"]):
        return "HAZARD"
    if any(k in cond_text for k in ["WET", "MOIST"]):
        return "WET"
    return "NORMAL"

def color_for_severity(sev: str) -> str:
    return {
        "HAZARD": "red",
        "WET": "orange",
        "NORMAL": "#4a90e2",
    }.get(sev, "gray")

# ----------------------------
# 3) FETCH DATA
# ----------------------------
print("Fetching road forecasts and warnings...")
forecasts, geometry = fetch_road_forecasts()
warnings = fetch_warnings()
print(f"  - Forecast sections: {len(geometry)}")
print(f"  - Traffic warnings: {len(warnings)}")

# ----------------------------
# 4) CREATE MAP
# ----------------------------
m = folium.Map(location=[center_lat, center_lon], zoom_start=11, control_scale=True)
MiniMap(toggle_display=True, position="bottomright").add_to(m)

# Feature layers
warnings_layer = FeatureGroup(name="🚧 Roadworks & Warnings", show=True)
weather_layer = FeatureGroup(name="🌡 Weather Stations", show=True)
camera_layer = FeatureGroup(name="📷 Cameras", show=True)
tms_layer = FeatureGroup(name="🚗 Traffic Measurement", show=True)

# ----------------------------
# 5) ADD MARKERS
# ----------------------------
def add_marker(coords, tooltip_html, color, icon, prefix="fa"):
    if not coords:
        return
    tooltip_html = tooltip_html.replace("\n", "<br>")
    folium.Marker(
        [coords["lat"], coords["lon"]],
        tooltip=folium.Tooltip(tooltip_html, sticky=True),
        icon=folium.Icon(color=color, icon=icon, prefix=prefix),
    ).add_to(m)

# Home and Ainola markers (always visible)
add_marker(HOME, HOME.get("tooltip", "Home"), color="blue", icon="home")
add_marker(AINOLA, AINOLA.get("tooltip", "Ainola Parking"), color="green", icon="train")

# ----------------------------
# 6) DRAW ROAD FORECAST SECTIONS
# ----------------------------
for feat in geometry:
    props = feat.get("properties", {})
    geom = feat.get("geometry", {})
    road_num = props.get("roadNumber")
    sec_id = props.get("id")
    desc = props.get("description", "")

    if road_num not in ROADS_OF_INTEREST:
        continue
    if geom.get("type") != "MultiLineString":
        continue

    cond_data = forecasts.get(sec_id, {})
    cond = cond_data.get("cond", "UNKNOWN")
    air_t = cond_data.get("airTemp", "?")
    road_t = cond_data.get("roadTemp", "?")
    ftime = cond_data.get("time", "")

    ftime_fmt = ""
    if ftime:
        try:
            ftime_fmt = datetime.fromisoformat(ftime.replace("Z", "+00:00")).strftime("%d.%m.%Y %H:%M")
        except Exception:
            ftime_fmt = ftime

    sev = classify_condition(cond)
    color = color_for_severity(sev)

    tooltip_html = (
        f"<b>Road {road_num}</b><br>"
        f"{desc}<br>"
        f"<b>Condition:</b> {cond}<br>"
        f"<b>Air T:</b> {air_t} °C<br>"
        f"<b>Road T:</b> {road_t} °C<br>"
        f"<b>Forecast:</b> {ftime_fmt}"
    )

    for segment in geom.get("coordinates", []):
        path = [(lat, lon) for lon, lat, *_ in segment]
        folium.PolyLine(
            locations=path,
            weight=5,
            color=color,
            opacity=0.85,
            tooltip=folium.Tooltip(tooltip_html, sticky=True),
        ).add_to(m)

# ----------------------------
# 7) ADD ROADWORKS / WARNINGS
# ----------------------------
for w in warnings:
    lon, lat = w.get("coordinates", (None, None))
    if not (lat and lon):
        continue

    tooltip_html = (
        f"<b>{w['type']}</b><br>"
        f"<b>Location:</b> {w['location']}<br>"
        f"<b>Start:</b> {w['start']}<br>"
        f"<b>Planned end:</b> {w['end']}<br>"
        f"<b>Restrictions:</b> {w['restrictions']}<br>"
        f"<b>ID:</b> {w['id']}"
    )

    folium.Marker(
        [lat, lon],
        icon=folium.Icon(color="orange", icon="wrench", prefix="fa"),
        tooltip=folium.Tooltip(tooltip_html, sticky=True),
    ).add_to(warnings_layer)

# ----------------------------
# 8) ADD SENSOR LAYERS
# ----------------------------
print("Fetching weather, camera, and TMS sensor data...")

# 🌡 Weather stations
for ws in fetch_weather_stations():
    tooltip_html = (
        f"🌡 <b>{ws['name']}</b><br>"
        f"Air: {ws['airTemp']} °C<br>"
        f"Road: {ws['roadTemp']} °C<br>"
        f"Wind: {ws['wind']} m/s<br>"
        f"Humidity: {ws['humidity']} %<br>"
        f"Precipitation: {ws['precipitation']}<br>"
        f"Condition: {ws['roadCondition']}"
    )
    folium.Marker(
        [ws["lat"], ws["lon"]],
        tooltip=folium.Tooltip(tooltip_html, sticky=True),
        icon=folium.Icon(color="lightgreen", icon="cloud", prefix="fa")
    ).add_to(weather_layer)

# 📷 Cameras
for cam in fetch_camera_stations():
    img_html = (
        f"<img src='{cam['images'][0]}' width='220'><br><small>{len(cam['images'])} view(s)</small>"
        if cam["images"] else "<i>No image available</i>"
    )
    tooltip_html = f"📷 <b>{cam['name']}</b><br>{img_html}"
    folium.Marker(
        [cam["lat"], cam["lon"]],
        tooltip=folium.Tooltip(tooltip_html, sticky=True),
        icon=folium.Icon(color="purple", icon="camera", prefix="fa")
    ).add_to(camera_layer)

# 🚗 TMS stations
for tms in fetch_tms_stations():
    speed = tms.get("speed")
    volume = tms.get("volume")
    tooltip_html = (
        f"🚗 <b>{tms['name']}</b><br>"
        f"Speed: {speed} km/h<br>"
        f"Volume: {volume} veh/h"
    )
    folium.Marker(
        [tms["lat"], tms["lon"]],
        tooltip=folium.Tooltip(tooltip_html, sticky=True),
        icon=folium.Icon(color="red", icon="car", prefix="fa")
    ).add_to(tms_layer)

# Add all feature layers to map
warnings_layer.add_to(m)
weather_layer.add_to(m)
camera_layer.add_to(m)
tms_layer.add_to(m)
LayerControl(collapsed=False).add_to(m)

# ----------------------------
# 9) ADD BOUNDING BOX FRAME (RED)
# ----------------------------
bbox_coords = [
    (Y_MIN, X_MIN),
    (Y_MIN, X_MAX),
    (Y_MAX, X_MAX),
    (Y_MAX, X_MIN),
    (Y_MIN, X_MIN),
]
folium.PolyLine(
    locations=bbox_coords,
    color="red",
    weight=3,
    opacity=0.9,
    dash_array="5,5",
    tooltip="Configured bounding box area",
).add_to(m)

# ----------------------------
# 10) LEGEND
# ----------------------------
legend_html = """
<div style="
position: absolute;
bottom: 30px; left: 30px; width: 130px;
background-color: white;
border:2px solid grey;
z-index:9999;
font-size:14px;
padding:10px;">
<b>Legend</b><br>
<svg height="10" width="20"><line x1="0" y1="5" x2="20" y2="5"
style="stroke:red;stroke-width:4"/></svg> Hazardous<br>
<svg height="10" width="20"><line x1="0" y1="5" x2="20" y2="5"
style="stroke:orange;stroke-width:4"/></svg> Wet / Moist<br>
<svg height="10" width="20"><line x1="0" y1="5" x2="20" y2="5"
style="stroke:#4a90e2;stroke-width:4"/></svg> Normal<br>
</div>
"""
m.get_root().html.add_child(folium.Element(legend_html))

# ----------------------------
# 11) SAVE MAP
# ----------------------------
if __name__ == "__main__":
    m.save("roads_map.html")
    print("✅ Saved map as roads_map.html — open it in your browser to preview.")

    import webbrowser
    import os

    file_path = os.path.abspath("roads_map.html")
    webbrowser.open(f"file://{file_path}")

