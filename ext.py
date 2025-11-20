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
