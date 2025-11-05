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
from datetime import datetime, timezone

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
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("🚆 Ainola Commute Dashboard")

# ----------------------------
# 3) WEATHER SUMMARY (TOP)
# ----------------------------
try:
    from weather import weather_at, set_config

    def safe_weather_at(time_str, place):
        """Call weather_at() safely, ensuring proper config and readable output."""
        try:
            set_config(place=place, forecast_hours=48)
            result = weather_at(time_str)
            # Ensure the output is a string (handle tuple unpacking errors internally)
            if isinstance(result, (list, tuple)):
                return "\n".join(map(str, result))
            return str(result)
        except Exception as e:
            return f"⚠️ {place}: {e}"

    places = [
        ("Paippinen", "Paippinen"),
        ("Kyrölä", "Ainola"),
        ("Helsinki", "Helsinki"),
    ]

    cols = st.columns(3)
    timestamp = datetime.now(timezone.utc).strftime("%H:%M UTC")

    for idx, (place, display_name) in enumerate(places):
        with cols[idx]:
            morning = safe_weather_at("08:00", place)
            afternoon = safe_weather_at("16:00", place)
            st.markdown(
                f"""
                <div class="weather-box">
                <strong>🌅 {display_name} 08:00</strong><br>
                {morning.replace('\n', '<br>')}
                <hr style="border:none;border-top:1px solid #ccc;margin:0.5em 0;">
                <strong>🌇 {display_name} 16:00</strong><br>
                {afternoon.replace('\n', '<br>')}
                </div>
                """,
                unsafe_allow_html=True,
            )

    st.markdown(
        f"<p style='font-size:0.85em;color:gray;text-align:center;'>Updated {timestamp}</p>",
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
