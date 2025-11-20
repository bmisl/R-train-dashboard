"""
main.py
--------
Streamlit dashboard combining:
- 🌦️ Weather forecast (from weather.py)
- 🚆 Train status and departures (from trains_display.py)
- 🛣️ Road and weather map (from roads_display.py)
- 🌧️ Live rain radar (Sataako.fi embed)

Behavior:
- Weather summary shows Paippinen daylight info and 4-hour forecast blocks for Järvenpää and Helsinki.
- Trains render immediately on first run.
- After trains are shown, the app triggers one rerun to load the roads map.
- Compact layout (minimal whitespace).
"""

import json
import os
import textwrap
from datetime import datetime, time as dtime
import zoneinfo

import streamlit as st

# ----------------------------
# 1) PAGE CONFIG
# ----------------------------
st.set_page_config(
    page_title="Commute Dashboard",
    page_icon="🚉",
    layout="wide",
)

# ----------------------------
# 2) GLOBAL CSS — tighten layout
# ----------------------------
st.markdown(
    """
    <style>
        .block-container {
            padding-top: 1.3rem !important;
            padding-bottom: 0.8rem !important;
        }
        h3, .stMarkdown h3 {
            margin-top: 0.4rem !important;
            margin-bottom: 0.4rem !important;
        }
        hr {
            margin-top: 0.4rem !important;
            margin-bottom: 0.4rem !important;
        }
        div[data-testid="stVerticalBlock"] {
            padding-top: 0rem !important;
            padding-bottom: 0rem !important;
        }
        .sun-card {
            background: #f5f7fb;
            border-radius: 0.75em;
            border: 1px solid rgba(48, 69, 98, 0.15);
            padding: 0.8em 1em;
            margin-bottom: 0.8em;
        }
        .sun-card h4 {
            margin: 0 0 0.4em 0;
            font-size: 1em;
            font-weight: 700;
        }
        .sun-card .sun-grid {
            display: flex;
            gap: 1.2em;
            flex-wrap: wrap;
        }
        .sun-card .sun-item {
            display: flex;
            flex-direction: column;
            font-size: 0.85em;
            color: #304562;
        }
        .sun-card .sun-item span {
            font-weight: 600;
            margin-bottom: 0.15em;
        }
        .forecast-card {
            background: #ffffff;
            border: 1px solid rgba(48, 69, 98, 0.12);
            border-radius: 0.75em;
            padding: 0.7em 0.85em;
            height: 100%;
        }
        .forecast-title {
            font-weight: 700;
            font-size: 1em;
            margin-bottom: 0.4em;
            text-align: center;
        }
        .forecast-range {
            font-size: 0.75em;
            color: #61728c;
            text-align: center;
            margin-bottom: 0.4em;
        }
        .forecast-row {
            display: grid;
            grid-template-columns: 1.3fr 0.9fr 1.8fr 1fr 1fr 1fr;
            align-items: center;
            gap: 0.4em;
            padding: 0.35em 0.2em;
            border-top: 1px solid rgba(0, 0, 0, 0.05);
            font-size: 0.78em;
        }
        .forecast-row:first-of-type {
            border-top: none;
        }
        .forecast-time {
            font-weight: 600;
            color: #1c2d44;
        }
        .forecast-icon {
            display: flex;
            justify-content: center;
            align-items: center;
        }
        .forecast-icon img {
            width: 32px;
            height: 32px;
        }
        .forecast-icon .fallback-icon {
            font-size: 1.3em;
        }
        .forecast-desc {
            color: #304562;
        }
        .forecast-metric {
            text-align: right;
            color: #1f3650;
            font-feature-settings: "tnum";
        }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("🚆 Ainola Commute Dashboard")

TZ = zoneinfo.ZoneInfo("Europe/Helsinki")

# ----------------------------
# 3) WEATHER SUMMARY (TOP)
# ----------------------------
try:
    from weather import daylight_summary, interval_forecast

    config_path = os.path.join(os.path.dirname(__file__), "config.json")
    config = {}
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)

    home_coords = config.get("HOME_COORDS", {})
    if home_coords:
        sun_info = daylight_summary(home_coords.get("lat"), home_coords.get("lon"))
        sunrise = sun_info.get("sunrise") or "—"
        sunset = sun_info.get("sunset") or "—"
        day_length = sun_info.get("day_length") or "—"
        sun_html = f"""
        <div class="sun-card">
            <h4>☀️ Paippinen daylight today</h4>
            <div class="sun-grid">
                <div class="sun-item"><span>Sunrise</span>{sunrise}</div>
                <div class="sun-item"><span>Sunset</span>{sunset}</div>
                <div class="sun-item"><span>Day length</span>{day_length}</div>
            </div>
        </div>
        """
        st.markdown(sun_html, unsafe_allow_html=True)

    def render_interval_card(column, title, place):
        data, error = interval_forecast(place)
        if error:
            column.error(error)
            return

        intervals = data.get("intervals", [])
        if not intervals:
            column.warning("No forecast data available.")
            return

        start = data.get("start")
        end = data.get("end")
        range_str = ""
        if start and end:
            range_str = f"{start.strftime('%a %d.%m %H:%M')} → {end.strftime('%a %d.%m %H:%M')}"

        def fmt_val(value, unit):
            if value is None:
                return "—"
            return f"{value:.1f} {unit}"

        rows_html = []
        for item in intervals:
            icon_html = (
                f"<img src='{item['icon_url']}' alt='{item['symbol_description']}' />"
                if item.get("icon_url")
                else "<span class='fallback-icon'>☁️</span>"
            )
            label = item.get("label", "")
            desc = item.get("symbol_description", "")
            temp_text = fmt_val(item.get("temperature_c"), "°C")
            rain_text = fmt_val(item.get("precip_mm"), "mm/h")
            wind_text = fmt_val(item.get("wind_ms"), "m/s")

            row_html = textwrap.dedent(
                f"""
                <div class="forecast-row">
                    <div class="forecast-time">{label}</div>
                    <div class="forecast-icon">{icon_html}</div>
                    <div class="forecast-desc">{desc}</div>
                    <div class="forecast-metric">{temp_text}</div>
                    <div class="forecast-metric">{rain_text}</div>
                    <div class="forecast-metric">{wind_text}</div>
                </div>
                """
            ).strip()
            rows_html.append(row_html)

        card_html = (
            "<div class=\"forecast-card\">"
            f"<div class=\"forecast-title\">{title}</div>"
            f"<div class=\"forecast-range\">{range_str}</div>"
            "<div class=\"forecast-rows\">"
            f"{''.join(rows_html)}"
            "</div>"
            "</div>"
        )
        column.markdown(card_html, unsafe_allow_html=True)

    cols = st.columns(2)
    render_interval_card(cols[0], "Järvenpää – 4h forecast blocks", "Järvenpää")
    render_interval_card(cols[1], "Helsinki – 4h forecast blocks", "Helsinki")

    timestamp = datetime.now().strftime("%H:%M")
    st.markdown(
        f"<p style='font-size:0.85em;color:gray;text-align:center;'>Updated at {timestamp}</p>",
        unsafe_allow_html=True,
    )

except Exception as e:
    st.warning(f"⚠️ Weather forecast unavailable: {e}")

# ----------------------------
# 4) TRAINS SECTION (IMMEDIATE)
# ----------------------------
with st.spinner("Loading live train data..."):
    try:
        from trains_display import render_trains_html
        trains_html = render_trains_html()
        st.components.v1.html(trains_html, height=550, scrolling=True)
    except Exception as e:
        st.error(f"❌ Failed to load train section: {e}")

st.markdown("<hr style='margin:0.4em 0; border: 1px solid #ccc;'>", unsafe_allow_html=True)

# ----------------------------
# 5) ROADS SECTION (DEFERRED LOAD)
# ----------------------------
if "phase" not in st.session_state:
    st.session_state.phase = 0

@st.cache_data(ttl=300)
def get_roads_html():
    """Build and return the Folium map HTML (cached for 5 min)."""
    from roads_display import m as roads_map
    return roads_map._repr_html_()

if st.session_state.phase == 0:
    st.info("Loading roads and sensors…")
    st.session_state.phase = 1
    st.rerun()
else:
    with st.spinner("Fetching road forecasts, weather, and sensors..."):
        try:
            html_map = get_roads_html()
            st.components.v1.html(html_map, height=700, scrolling=False)
        except Exception as e:
            st.error(f"❌ Failed to load road map: {e}")

# ----------------------------
# 6) RAIN RADAR EMBED (Sataako.fi)
# ----------------------------
st.markdown("<hr style='margin:0.4em 0;'>", unsafe_allow_html=True)
st.subheader("🌧️ Live Rain Radar")

# Helsinki-area centered map, side panel collapsed
sataako_url = "https://www.sataako.fi?x=2776307.5&y=8438349.3&zoom=8&collapsed=true"

st.components.v1.iframe(
    sataako_url,
    height=700,
    scrolling=False,
)


# ----------------------------
# 6b) AFTERNOON AUDIO ANNOUNCEMENT HELPERS
# ----------------------------
def announcement_window_active(now=None):
    """Return True between 15:00–17:00 Helsinki time."""
    now = now or datetime.now(TZ)
    return dtime(15, 0) <= now.time() < dtime(17, 0)


def next_helsinki_departure_text():
    """Return spoken text for the next R-train leaving Helsinki."""
    try:
        from trains import get_trains, load_config

        cfg = load_config()
        home = cfg.get("HOME_STATIONS", {})
        origin = home.get("destination", "HKI")
        dest = home.get("origin", "AIN")

        departures = get_trains(origin, dest)
        if not departures:
            return None, "No R-train departures available right now."

        sched_time, _, _, best_dt, platform, _ = departures[0]
        dep_dt = (best_dt or sched_time).astimezone(TZ)
        time_str = dep_dt.strftime("%H:%M")
        track = platform or "—"
        return f"Next R-train leaves from track {track} at {time_str}.", None
    except Exception as exc:  # pragma: no cover - defensive guard for runtime errors
        return None, f"Unable to fetch departure info: {exc}"

# ----------------------------
# 7) FOOTER
# ----------------------------
st.markdown("<hr style='margin:0.4em 0;'>", unsafe_allow_html=True)
st.subheader("🔗 External resources")
st.markdown(
    "Explore the detailed FMI local forecast for Paippinen and live Junalahdot departure boards.",
    help="Embedded pages load from en.ilmatieteenlaitos.fi and junalahdot.fi.",
)

st.components.v1.iframe(
    "https://en.ilmatieteenlaitos.fi/local-weather/sipoo/paippinen",
    height=820,
    scrolling=True,
)

train_cols = st.columns([1, 0.45, 1])
with train_cols[0]:
    st.components.v1.iframe(
        "https://junalahdot.fi/518952272?command=fs&id=219&dt=dep&lang=3&did=47&title=Ainola%20-%20Helsinki",
        height=520,
        scrolling=True,
    )

with train_cols[1]:
    if announcement_window_active():
        st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)
        if st.button("🔈 Hear next Helsinki R-train", use_container_width=True):
            announcement, err = next_helsinki_departure_text()
            if err:
                st.warning(err)
            elif announcement:
                st.success(announcement)
                safe_text = json.dumps(announcement)
                st.components.v1.html(
                    f"""
                    <script>
                        const text = {safe_text};
                        const msg = new SpeechSynthesisUtterance(text);
                        window.speechSynthesis.cancel();
                        window.speechSynthesis.speak(msg);
                    </script>
                    """,
                    height=0,
                )
    else:
        st.markdown(" ")

with train_cols[2]:
    st.components.v1.iframe(
        "https://junalahdot.fi/518952272?command=fs&id=47&dt=dep&lang=3&did=219&title=Helsinki%20-%20Ainola",
        height=520,
        scrolling=True,
    )

st.markdown("<hr style='margin:0.4em 0;'>", unsafe_allow_html=True)
st.caption(
    "Data from FMI and Digitraffic.fi — trains render immediately; "
    "roads and sensors load after. Roads map cached for 5 minutes. "
    "Weather forecasts courtesy of FMI Open Data and Sataako.fi."
)
