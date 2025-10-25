import streamlit as st
import folium
from streamlit_folium import st_folium
from folium.plugins import MarkerCluster
from datetime import datetime, time as dtime, timedelta, timezone
import zoneinfo

from trains import (
    get_trains,
    fetch_station_names,
    final_destination_name,
    parse_time,
    format_hki,
    heading_md,  # NEW: underline support for active column
)

from roads import (
    fetch_road_geometry,
    fetch_road_forecasts,
    fetch_warnings,
    is_hazard,
    color_for_condition,
)

# ----------------------------
# CONSTANTS
# ----------------------------
HKI = "HKI"
AIN = "AIN"
TZ = zoneinfo.ZoneInfo("Europe/Helsinki")
X_MIN, Y_MIN = 25.00, 60.40
X_MAX, Y_MAX = 25.30, 60.55

AINOLA_LAT = 60.4553286
AINOLA_LON = 25.0983628
HOME_LAT = 60.4445786
HOME_LON = 25.2428331

BOUNDING_BOX = [
    [Y_MIN, X_MIN], [Y_MAX, X_MIN],
    [Y_MAX, X_MAX], [Y_MIN, X_MAX],
    [Y_MIN, X_MIN]
]

# ----------------------------
# PAGE CONFIG
# ----------------------------
st.set_page_config(page_title="Ainola ↔ Helsinki R-trains", page_icon="🚆", layout="wide")

# Show UI instantly — placeholder before data is loaded
st.title("🚆 Ainola ↔ Helsinki R-trains")
loading_placeholder = st.empty()
loading_placeholder.info("⏳ Loading train and road data...")

# ----------------------------
# UTILS
# ----------------------------
def helsinki_now():
    return datetime.now(TZ)

now_utc = datetime.now(timezone.utc)

# ----------------------------
# 🚆 TRAIN DATA — Cached for 30s
# ----------------------------
if "train_data" not in st.session_state:
    st.session_state["train_data"] = {
        "timestamp": None,
        "station_names": None,
        "trains_A_to_H": None,
        "trains_H_to_A": None
    }

train_cache = st.session_state["train_data"]

if (train_cache["timestamp"] is None or
    (now_utc - train_cache["timestamp"]) > timedelta(seconds=30)):
    st.session_state["train_data"] = {
        "timestamp": now_utc,
        "station_names": fetch_station_names(),
        "trains_A_to_H": get_trains(AIN, HKI),
        "trains_H_to_A": get_trains(HKI, AIN)
    }

station_names = st.session_state["train_data"]["station_names"]
trains_A_to_H = st.session_state["train_data"]["trains_A_to_H"]
trains_H_to_A = st.session_state["train_data"]["trains_H_to_A"]

# ----------------------------
# 🛣 ROAD DATA — Cached 5 minutes
# ----------------------------
if "road_data" not in st.session_state:
    st.session_state["road_data"] = {
        "timestamp": None,
        "geometry": None,
        "forecasts": None,
        "warnings": None
    }

def refresh_roads():
    st.session_state["road_data"] = {
        "timestamp": datetime.now(timezone.utc),
        "geometry": fetch_road_geometry(),
        "forecasts": fetch_road_forecasts(),
        "warnings": fetch_warnings()
    }

roads_expired = (
    st.session_state["road_data"]["timestamp"] is None or
    (now_utc - st.session_state["road_data"]["timestamp"]) > timedelta(minutes=5)
)

if roads_expired:
    refresh_roads()

geometry = st.session_state["road_data"]["geometry"]
forecasts = st.session_state["road_data"]["forecasts"]
warnings = st.session_state["road_data"]["warnings"]

# ✅ Remove loading indicator once data is fetched
loading_placeholder.empty()

# ----------------------------
# ROADWORKS FORMATTER
# ----------------------------
def format_roadworks(warnings_list):
    """
    Convert Digitraffic warnings into a clean list of roadworks dictionaries.
    Each item:
      {
        "id": <situationId>,
        "road": <roadName>,
        "municipality": <municipality>,
        "start": <'DD Month YYYY'>,
        "lat": <float>,
        "lon": <float>,
      }
    Only ROAD_WORK items are included. Assumes warnings already filtered to bounding box.
    """
    out = []
    for w in warnings_list or []:
        props = w.get("props", {})
        if props.get("situationType") != "ROAD_WORK":
            continue

        announcements = props.get("announcements", [])
        ann = announcements[0] if announcements else {}
        primary = (ann.get("locationDetails", {}) or {}) \
                    .get("roadAddressLocation", {}) \
                    .get("primaryPoint", {})

        road_name = primary.get("roadName", "Unknown road")
        muni = primary.get("municipality", "Unknown area")

        # releaseTime as start
        release_time = props.get("releaseTime")
        try:
            start = datetime.fromisoformat(release_time.replace("Z", "+00:00")).strftime("%d %B %Y")
        except Exception:
            start = release_time or "Unknown start"

        out.append({
            "id": props.get("situationId"),
            "road": road_name,
            "municipality": muni,
            "start": start,
            "lat": w.get("lat"),
            "lon": w.get("lon"),
        })
    return out

# ----------------------------
# UI HEADER
# ----------------------------
now_local = helsinki_now().time()
focus_H_to_A = dtime(12, 0) <= now_local < dtime(17, 0)
focus_label = "Helsinki → Ainola" if focus_H_to_A else "Ainola → Helsinki"

# ----------------------------
# NEXT TRAIN SELECTION
# ----------------------------
active_trains = trains_H_to_A if focus_H_to_A else trains_A_to_H
next_train = None
for sched, num, text, best_time, platform, rows in active_trains:
    if best_time >= now_utc:
        next_train = (num, text, platform, rows, sched)
        break

# ----------------------------
# TRAIN LISTS
# ----------------------------
col1, col2 = st.columns(2)

def render_train_column(col, trains, title, active):
    # Underline active column heading
    col.markdown(heading_md(title, active), unsafe_allow_html=True)

    for sched, num, text, best, platform, rows in trains:
        dest = final_destination_name(rows, station_names)
        line = f"To {dest} (R {num}) — {text}"
        if next_train and num == next_train[0] and active:
            col.markdown(
                f"<span style='background-color:rgba(200,200,200,0.3);padding:4px;border-radius:4px;'>{line}</span>",
                unsafe_allow_html=True
            )
        else:
            col.write(line)

render_train_column(col1, trains_A_to_H, "Ainola → Helsinki", not focus_H_to_A)
render_train_column(col2, trains_H_to_A, "Helsinki → Ainola", focus_H_to_A)

# ----------------------------
# NEXT TRAIN INFO
# ----------------------------
st.markdown("---")
if next_train:
    num, time_text, platform, rows, sched_time = next_train
    mins = int((sched_time - now_utc).total_seconds() / 60)
    dest = final_destination_name(rows, station_names)
    target = AIN if focus_H_to_A else HKI
    arr = next((r for r in rows if r["stationShortCode"] == target and r["type"] == "ARRIVAL"), None)
    arr_time = format_hki(parse_time(arr["scheduledTime"])) if arr else "—"

    st.subheader(f"⬇ Next train ({focus_label})")
    st.markdown(
        f"<span style='background-color: rgba(200,200,200,0.3); "
        f"padding:6px 8px; border-radius:6px; display:inline-block;'>"
        f"<b>To {dest} (R {num})</b> — Departs {time_text} "
        f"<i>(in {mins} min)</i> | Platform: {platform}"
        f"</span>",
        unsafe_allow_html=True
    )
    st.write(f"Arrives at {station_names[target]}: {arr_time}")
else:
    st.info("No upcoming trains.")

# ----------------------------
# ROAD CONDITIONS / WARNINGS
# ----------------------------
st.markdown("---")
if geometry is None:
    st.info("⏳ Road & traffic data pending...")
else:
    st.subheader("🛣 Road Conditions")
    hazardous = []
    for feat in geometry:
        props = feat.get("properties", {})
        if props.get("roadNumber") in (140, 145, 146):
            sid = props.get("id")
            cond = forecasts.get(sid, {}).get("cond")
            if cond and is_hazard(cond):
                hazardous.append((props.get("roadNumber"), props.get("description"), cond))

    if hazardous:
        for road, desc, cond in hazardous:
            st.write(f"**Road {road} – {desc}** | {cond}")
    else:
        st.success("✅ No hazardous conditions.")

    # ✅ Use formatted roadworks
    st.subheader("👷 Roadworks Nearby")
    roadworks = format_roadworks(warnings)

    if roadworks:
        for rw in roadworks:
            st.write(f"• **Road: {rw['road']} in {rw['municipality']}**")
            st.write(f"  🕒 Start: {rw['start']}")
    else:
        st.success("✅ No active roadworks near Ainola.")

    # ----------------------------
    # MAP
    # ----------------------------
    st.subheader("🗺 Map — Roads, Warnings, Ainola & Home")
    try:
        m = folium.Map(location=[(Y_MIN + Y_MAX) / 2, (X_MIN + X_MAX) / 2], zoom_start=12)
        folium.Polygon(BOUNDING_BOX, color="red", weight=2).add_to(m)

        folium.Marker([AINOLA_LAT, AINOLA_LON], tooltip="Ainola Station",
                      icon=folium.Icon(color="green", icon="train")).add_to(m)
        folium.CircleMarker([HOME_LAT, HOME_LON], radius=6, color="blue", fill=True,
                            tooltip="Home").add_to(m)

        for feat in geometry:
            geom = feat.get("geometry", {})
            if geom.get("type") == "MultiLineString":
                sid = feat.get("properties", {}).get("id")
                cond = forecasts.get(sid, {}).get("cond")
                color = color_for_condition(cond)
                for line in geom["coordinates"]:
                    coords = [(lat, lon) for lon, lat, *_ in line]
                    folium.PolyLine(coords, color=color, weight=4).add_to(m)

        # Build a quick lookup for tooltips keyed by situationId
        rw_lookup = {rw["id"]: f"{rw['road']} — {rw['municipality']}" for rw in roadworks}

        if warnings:
            cluster = MarkerCluster().add_to(m)
            for w in warnings:
                props = w.get("props", {})
                sid = props.get("situationId")
                if props.get("situationType") == "ROAD_WORK":
                    tooltip_text = rw_lookup.get(sid, "Road work")
                else:
                    tooltip_text = f"{props.get('situationType')}: {props.get('title', '(no title)')}"

                folium.Marker(
                    [w["lat"], w["lon"]],
                    tooltip=tooltip_text,
                    icon=folium.Icon(color="red", icon="exclamation-triangle", prefix="fa")
                ).add_to(cluster)

        st_folium(m, height=550, width=None)
    except Exception as e:
        st.error(f"Error rendering map: {e}")
