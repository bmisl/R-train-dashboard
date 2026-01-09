# ext.py
"""
Streamlit commute dashboard with embedded external resources.
"""

import json
import requests
from datetime import datetime, time
from typing import List, Tuple, Optional
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from zoneinfo import ZoneInfo

import streamlit as st
import weather
from movie_picker import movie_spotlight
import fingrid_prices

# Constants
TZ = ZoneInfo("Europe/Helsinki")
MORNING_PEAK_START = time(6, 0)
MORNING_PEAK_END = time(14, 0)

# Page configuration
st.set_page_config(
    page_title="Commute Dashboard – My Commute",
    page_icon="🌐",
    layout="wide",
)

# Styles
STYLES = """
<style>
    .section-header {
        display: flex;
        align-items: center;
        gap: 0.6rem;
        margin: 1.5rem 0 0.75rem 0;
    }
    .section-title {
        font-size: 1.25rem;
        font-weight: 700;
        margin: 0;
    }
    .section-icon {
        font-size: 1.2rem;
    }
    .embed-frame {
        border: 1px solid rgba(0, 0, 0, 0.08);
        border-radius: 0.75rem;
        overflow: hidden;
        box-shadow: 0 4px 14px rgba(17, 24, 39, 0.08);
        background: #ffffff;
    }
    .embed-frame iframe {
        width: 100%;
        height: 100%;
        border: 0;
    }
    .embed-wrapper {
        margin-bottom: 1.2rem;
    }
    .embed-title {
        font-weight: 600;
        margin-bottom: 0.35rem;
    }
    .narrow-frame {
        max-width: 900px;
        margin: 0;
    }
    @media (max-width: 640px) {
        .narrow-frame {
            max-width: 92vw;
        }
    }
</style>
"""


def ensure_main_fragment(url: str) -> str:
    """Append view=main and #main for FMI pages."""
    if "ilmatieteenlaitos.fi" not in url:
        return url

    split = urlsplit(url)
    params = dict(parse_qsl(split.query, keep_blank_values=True))
    params.setdefault("view", "main")
    query = urlencode(params, doseq=True)
    return urlunsplit((split.scheme, split.netloc, split.path, query, "main"))


def get_departure_info(direction: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Get departure announcement for specified direction.

    Args:
        direction: 'to_helsinki' or 'from_helsinki'

    Returns:
        (announcement_text, error_message)
    """
    try:
        from trains import get_trains, load_config

        cfg = load_config()
        stations = cfg.get("HOME_STATIONS", {})

        if direction == "to_helsinki":
            origin = stations.get("origin", "AIN")
            dest = stations.get("destination", "HKI")
            origin_name = "Ainola"
        else:
            origin = stations.get("destination", "HKI")
            dest = stations.get("origin", "AIN")
            origin_name = "Helsinki"

        departures = get_trains(origin, dest)
        if not departures:
            return None, f"No departures from {origin_name}"

        sched_time, _, _, best_dt, platform, _ = departures[0]
        dep_dt = (best_dt or sched_time).astimezone(TZ)
        time_str = dep_dt.strftime("%H:%M")
        track = platform or "unknown"

        # Exact phrase:
        # "Track X at HH:MM."
        return f"Track {track}, at {time_str}.", None

    except Exception as exc:
        return None, str(exc)


def render_train_departures() -> None:
    """Render live train departure boards with voice announcements."""

    # --- Fetch data ---
    to_hki_text, to_hki_error = get_departure_info("to_helsinki")
    from_hki_text, from_hki_error = get_departure_info("from_helsinki")

    if to_hki_error:
        st.warning(f"Ainola → Helsinki: {to_hki_error}")
    if from_hki_error:
        st.warning(f"Helsinki → Ainola: {from_hki_error}")

    # --- Convert to JSON for JS ---
    to_hki_js = json.dumps(to_hki_text or "")
    from_hki_js = json.dumps(from_hki_text or "")

    # --- Build left card ---
    train_html_left = f"""
    <style>
        .train-card {{
            border: 1px solid rgba(0, 0, 0, 0.08);
            border-radius: 0.75rem;
            overflow: hidden;
            box-shadow: 0 4px 14px rgba(17, 24, 39, 0.08);
            background: #ffffff;
            height: 210px;
            position: relative;
        }}
        .train-card iframe {{
            width: 303%;
            height: 640px;
            transform: scale(0.33);
            transform-origin: top left;
            border: 0;
        }}
        .voice-btn {{
            position: absolute;
            inset: 0;
            background: transparent;
            border: none;
            cursor: pointer;
            z-index: 2;
        }}
        .voice-btn:hover {{
            background: rgba(0, 0, 0, 0.02);
        }}
    </style>

    <div class="train-card">
        <button class="voice-btn" data-dir="to_hki"
                aria-label="Hear next train from Ainola"></button>

        <iframe src="https://junalahdot.fi/518952272?command=fs&id=219&dt=dep&lang=3&did=47&title=Ainola%20-%20Helsinki"
                loading="lazy"></iframe>
    </div>

    <script>
    (function() {{
        const announceText = {to_hki_js};

        function speak(text) {{
            if (!text || !window.speechSynthesis) return;
            window.speechSynthesis.cancel();

            const utter = new SpeechSynthesisUtterance(text);

            const setVoice = () => {{
                const voices = window.speechSynthesis.getVoices();
                if (voices.length) {{
                    utter.voice =
                        voices.find(v => v.lang.toLowerCase().startsWith('en-gb')) ||
                        voices.find(v => v.lang.toLowerCase().startsWith('en')) ||
                        voices[0];
                }}
            }};

            if (window.speechSynthesis.getVoices().length)
                setVoice();
            else
                window.speechSynthesis.onvoiceschanged = setVoice;

            window.speechSynthesis.speak(utter);
        }}

        const btn = document.querySelector('.voice-btn[data-dir="to_hki"]');
        if (btn && !btn.dataset.bound) {{
            btn.dataset.bound = "true";
            btn.addEventListener('click', (e) => {{
                e.preventDefault();
                speak(announceText);
            }});
        }}
    }})();
    </script>
    """

    # --- Build right card ---
    train_html_right = f"""
    <style>
        .train-card {{
            border: 1px solid rgba(0, 0, 0, 0.08);
            border-radius: 0.75rem;
            overflow: hidden;
            box-shadow: 0 4px 14px rgba(17, 24, 39, 0.08);
            background: #ffffff;
            height: 210px;
            position: relative;
        }}
        .train-card iframe {{
            width: 303%;
            height: 640px;
            transform: scale(0.33);
            transform-origin: top left;
            border: 0;
        }}
        .voice-btn {{
            position: absolute;
            inset: 0;
            background: transparent;
            border: none;
            cursor: pointer;
            z-index: 2;
        }}
        .voice-btn:hover {{
            background: rgba(0, 0, 0, 0.02);
        }}
    </style>

    <div class="train-card">
        <button class="voice-btn" data-dir="from_hki"
                aria-label="Hear next train from Helsinki"></button>

        <iframe src="https://junalahdot.fi/518952272?command=fs&id=47&dt=dep&lang=3&did=219&title=Helsinki%20-%20Ainola"
                loading="lazy"></iframe>
    </div>

    <script>
    (function() {{
        const announceText = {from_hki_js};

        function speak(text) {{
            if (!text || !window.speechSynthesis) return;
            window.speechSynthesis.cancel();

            const utter = new SpeechSynthesisUtterance(text);

            const setVoice = () => {{
                const voices = window.speechSynthesis.getVoices();
                if (voices.length) {{
                    utter.voice =
                        voices.find(v => v.lang.toLowerCase().startsWith('en-gb')) ||
                        voices.find(v => v.lang.toLowerCase().startsWith('en')) ||
                        voices[0];
                }}
            }};

            if (window.speechSynthesis.getVoices().length)
                setVoice();
            else
                window.speechSynthesis.onvoiceschanged = setVoice;

            window.speechSynthesis.speak(utter);
        }}

        const btn = document.querySelector('.voice-btn[data-dir="from_hki"]');
        if (btn && !btn.dataset.bound) {{
            btn.dataset.bound = "true";
            btn.addEventListener('click', (e) => {{
                e.preventDefault();
                speak(announceText);
            }});
        }}
    }})();
    </script>
    """

    # --- Render in two columns ---
    col1, col2 = st.columns(2)
    with col1:
        st.components.v1.html(train_html_left, height=280, scrolling=False)
    with col2:
        st.components.v1.html(train_html_right, height=280, scrolling=False)

######################
# After train sections
######################

def render_live_train_map() -> None:
    """Render live R-train map during morning peak hours."""
    helsinki_time = datetime.now(TZ).time()
    if MORNING_PEAK_START <= helsinki_time < MORNING_PEAK_END:
        st.markdown(
            """
            <div class="embed-wrapper" style="max-width: 480px;">
                <div class="embed-title">Live R-Train Map (morning peak)</div>
                <div class="embed-frame" style="position: relative; padding-bottom: 75%; height: 0;">
                    <iframe
                        src="https://14142.net/kartalla/index.en.html?data=hsl&lat=60.475&lng=25.1&zoom=13&types=train&routes=R"
                        title="Live Train Map"
                        loading="lazy"
                        style="position: absolute; top: 0; left: 0; width: 100%; height: 100%;">
                    </iframe>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

def render_weather_alert() -> None:
    """Display weather alert if conditions warrant attention."""
    needs_attention, icon, details = weather.rough_weather_check()
    if needs_attention:
        st.markdown(f"### {icon} Commute weather alert")
        st.markdown(details)


def render_electricity_prices() -> None:
    """Display electricity prices for ±24 hours as a highly customized Altair chart."""
    st.markdown("### ⚡ Electricity Prices (±24h)")
    
    try:
        # Fetch price data using sähkötin.fi logic (accurate spot prices)
        price_data = fingrid_prices.get_plus_minus_24h_prices()
        
        if not price_data:
            st.warning("No electricity price data available for the ±24h period.")
            return
        
        # Prepare DataFrame
        import pandas as pd
        import altair as alt
        from datetime import datetime
        
        df = pd.DataFrame(price_data)
        df['localTime'] = pd.to_datetime(df['localTime'])
        df['localEndTime'] = pd.to_datetime(df['localEndTime'])
        now = datetime.now(fingrid_prices.TZ)
        
        # 1. Add "Type" for color coding (Past/Future)
        df['Period'] = df['localTime'].apply(lambda x: 'Past' if x < now else 'Future')
        
        # 2. Identify Highlights (2 cheapest and 2 most expensive slots)
        # We sort by value and take indices
        sorted_df = df.sort_values('value')
        cheapest_indices = sorted_df.head(8).index # 8 slots = 2 hours
        expensive_indices = sorted_df.tail(8).index # 8 slots = 2 hours
        
        # 3. Calculate Colors in DataFrame for stability
        def get_color(row):
            if row.name in cheapest_indices:
                return '#2ecc71' # Green
            if row.name in expensive_indices:
                return '#e74c3c' # Red
            if row['Period'] == 'Past':
                return '#3498db' # Blue
            return '#bdc3c7'      # Grey
            
        df['color'] = df.apply(get_color, axis=1)
        
        # Create Altair Chart
        chart = alt.Chart(df).mark_bar(
            stroke=None
        ).encode(
            x=alt.X('localTime:T', 
                    title=None,
                    axis=alt.Axis(format='%H:%M', labelAngle=0, grid=False)),
            x2='localEndTime:T', # Enforce width to the next 15-min mark
            y=alt.Y('value:Q', title='snt/kWh'),
            y2=alt.value(0),      # Extend bars to the base
            color=alt.Color('color:N', scale=None), # Use pre-calculated colors
            tooltip=[
                alt.Tooltip('localTime:T', title='Date/Time', format='%d.%m. %H:%M'),
                alt.Tooltip('value:Q', title='Price (snt/kWh)', format='.2f')
            ]
        ).properties(
            height=400,
        )
        
        # Add a vertical line for Midnight
        # Find the midnight timestamp between today and tomorrow
        tomorrow_start = now.replace(hour=0, minute=0, second=0, microsecond=0) + pd.Timedelta(days=1)
        midnight_line = alt.Chart(pd.DataFrame({'x': [tomorrow_start]})).mark_rule(
            color='white',
            strokeDash=[5, 5],
            strokeWidth=2
        ).encode(x='x:T')
        
        # Combine chart and line
        # Note: Config must be applied to the LAYERED chart, not the base chart
        final_chart = (chart + midnight_line).interactive().configure_view(
            strokeWidth=0
        )
        
        # Statistics summary
        summary = fingrid_prices.get_price_summary(price_data)
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Average", f"{summary['avg']:.2f} snt/kWh")
        with col2:
            st.metric("Min", f"{summary['min']:.2f} snt/kWh")
        with col3:
            st.metric("Max", f"{summary['max']:.2f} snt/kWh")
            
        st.altair_chart(final_chart, use_container_width=True)
        
        st.caption("💡 Spot prices from Sähkötin.fi API (incl. VAT and standard fees). Blue=Past, Grey=Future, Green=Cheapest 2h, Red=Expensive 2h.")
        
    except Exception as e:
        st.error(f"⚠️ Could not fetch electricity prices: {e}")
        st.info("Please check your internet connection.")


def render_embed(title: str, url: str, height: int, narrow: bool = False) -> None:
    """Render a generic iframe embed."""
    resolved_url = ensure_main_fragment(url)
    frame_class = "embed-frame narrow-frame" if narrow else "embed-frame"

    st.markdown(
        f"""
        <div class="embed-wrapper">
            <div class="embed-title">{title}</div>
            <div class="{frame_class}" style="height: {height}px;">
                <iframe src="{resolved_url}" loading="lazy" title="{title}"></iframe>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_joke() -> None:
    """Fetch and display a random joke."""
    try:
        response = requests.get(
            "https://official-joke-api.appspot.com/random_joke",
            timeout=10,
        )
        response.raise_for_status()
        joke = response.json()
        st.subheader("💬 Joke of the Day")
        st.markdown(f"**{joke['setup']}**  \n{joke['punchline']}")
    except Exception as e:
        st.error(f"Could not fetch joke: {e}")


def main() -> None:
    """Main application flow."""
    st.title("🌐 My Commute")
    st.markdown(STYLES, unsafe_allow_html=True)

    # Train departures
    render_train_departures()
    render_live_train_map()

    # Weather
    render_weather_alert()

    # Electricity prices
    render_electricity_prices()

    # External embeds
    embeds: List[Tuple[str, str, int, bool]] = [
        (
            "Paippinen Local Weather",
            "https://en.ilmatieteenlaitos.fi/local-weather/sipoo/paippinen",
            900,
            True,
        ),
        (
            "Traffic Situation Map",
            "https://liikennetilanne.fintraffic.fi/kartta/?lang=en&x=2797894.2876217626&y=8496601.610954674&z=11&checkedLayers=4,8&basemap=streets-vector&time=28_0&iframe=true",
            400,
            False,
        ),
        (
            "Aurora & Space Weather (Nurmijärvi)",
            "https://www.ilmatieteenlaitos.fi/revontulet-ja-avaruussaa?station=NUR",
            900,
            True,
        ),
    ]

    for title, url, height, narrow in embeds:
        render_embed(title, url, height, narrow)

    # Misc section
    st.title("😂 Misc")
    render_joke()
    movie_spotlight()


if __name__ == "__main__":
    main()
