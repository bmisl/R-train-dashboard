"""
main.py
--------
Streamlit dashboard combining:
- 🌦️ Weather forecast (from weather.py)
- 🚆 Train status and departures (from trains_display.py)
- 🛣️ Road and weather map (from roads_display.py)
- 🌧️ Live rain radar (Sataako.fi embed)

Behavior:
- Weather summary shown first (Paippinen, Ainola, Helsinki at 08:00 and 16:00)
- Trains render immediately on first run.
- After trains are shown, the app triggers one rerun to load the roads map.
- Compact layout (minimal whitespace).
"""

import streamlit as st
from datetime import datetime

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
        .weather-box {
            background-color: #eef6ff;
            padding: 0.6em 1em;
            border-radius: 0.8em;
            margin-bottom: 0.4em;
            box-shadow: 0 0 3px rgba(0,0,0,0.1);
            height: 100%;
        }
        .metric-line {
            display: flex;
            align-items: center;
            gap: 0.5em;
            font-size: 0.95em;
            margin: 0.25em 0;
        }
        .metric-icon {
            font-size: 1.25em;
            width: 1.6em;
        }
        .metric-label {
            font-weight: 600;
        }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("🚆 Ainola Commute Dashboard")

# ----------------------------
# 3) WEATHER SUMMARY (TOP)
# ----------------------------
try:
    from weather import weather_metrics, set_config

    def safe_weather_metrics(time_str, place):
        """Fetch metrics for a place/time combo, returning (metrics, error)."""
        try:
            set_config(place=place, forecast_hours=48)
            metrics, error = weather_metrics(time_str)
            if error:
                return None, error
            return metrics, None
        except Exception as e:
            return None, f"❌ {e}"

    def render_weather_card(column, title, place, time_str):
        metrics, error = safe_weather_metrics(time_str, place)
        if error:
            column.markdown(
                f"""
                <div class="weather-box">
                    <strong>{title}</strong>
                    <div style="margin-top:0.4em;">{error}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            return

        rain_mm = metrics["rain_mm"]
        temp_c = metrics["temperature_c"]
        wind_ms = metrics["wind_ms"]

        if rain_mm >= 1.0:
            rain_icon = "☂️"
        elif rain_mm >= 0.1:
            rain_icon = "🌦️"
        else:
            rain_icon = "☀️"

        temp_icon = "❄️" if temp_c < 0 else "🌡️"
        wind_icon = "💨" if wind_ms >= 5 else "🍃"

        metric_lines = [
            (rain_icon, "Rain", f"{rain_mm:.1f} mm/h"),
            (temp_icon, "Temperature", f"{temp_c:.1f} °C"),
            (wind_icon, "Wind", f"{wind_ms:.1f} m/s"),
        ]

        lines_html = "".join(
            f"<div class='metric-line'><span class='metric-icon'>{icon}</span>"
            f"<span class='metric-label'>{label}:</span> {value}</div>"
            for icon, label, value in metric_lines
        )

        column.markdown(
            f"""
            <div class="weather-box">
                <strong>{title}</strong>
                <div style="margin-top:0.4em;">
                    {lines_html}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    cols = st.columns(2)
    render_weather_card(cols[0], "🌅 Järvenpää 08:00", "Järvenpää", "08:00")
    render_weather_card(cols[1], "🌇 Helsinki 16:00", "Helsinki", "16:00")

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
# 7) FOOTER
# ----------------------------
st.markdown("<hr style='margin:0.4em 0;'>", unsafe_allow_html=True)
st.caption(
    "Data from FMI and Digitraffic.fi — trains render immediately; "
    "roads and sensors load after. Roads map cached for 5 minutes. "
    "Weather forecasts courtesy of FMI Open Data and Sataako.fi."
)
