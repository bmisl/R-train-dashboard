"""ext.py

Standalone Streamlit page with embedded external resources.
"""

import json
from datetime import datetime, time
from typing import List, Tuple
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from movie_picker import movie_spotlight

import streamlit as st
import weather
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Europe/Helsinki")

st.set_page_config(
    page_title="Commute Dashboard – My Commute",
    page_icon="🌐",
    layout="wide",
)

st.title("🌐 My Commute")

st.markdown(
    """
    <style>
        .train-header {
            display: flex;
            align-items: center;
            gap: 0.6rem;
            margin: 0.25rem 0 0.75rem 0;
        }
        .train-title {
            font-size: 1.25rem;
            font-weight: 700;
            margin: 0;
        }
        .train-title-icon {
            font-size: 1.2rem;
        }
        .train-audio-btn {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            width: 2.4rem;
            height: 2.4rem;
            border-radius: 0.75rem;
            border: none;
            cursor: pointer;
            font-size: 1.3rem;
            background: linear-gradient(135deg, #2563eb, #1d4ed8);
            color: #fff;
            box-shadow: 0 8px 20px rgba(37, 99, 235, 0.28);
        }
        .train-audio-btn:active {
            transform: translateY(1px);
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
       .train-grid {
            display: flex;
            gap: 1.2rem;
            flex-wrap: wrap;
            justify-content: flex-start;
        }

        .train-card {
            flex: 0 1 310px;  /* can shrink, but not grow beyond 310px */
            width: 310px;     /* sets the intended max width */
            max-width: 310px; /* ensures it won’t exceed this width */
            min-width: 250px; /* optional: allows a bit of shrink if needed */
        }

        .train-embed {
            height: 210px;
            position: relative;
        }

        .train-embed iframe {
            width: 303%;
            height: 640px;
            transform: scale(0.33);
            transform-origin: top left;
        }
        .narrow-frame {
            max-width: 900px;
            margin: 0;
        }
        @media (max-width: 900px) {
            .train-grid {
                flex-direction: column;
            }
            .train-card {
                flex: 1 1 auto;
            }
        }
        @media (max-width: 640px) {
            .narrow-frame {
                max-width: 92vw;
            }
        }
    </style>
    """,
    unsafe_allow_html=True,
)


def ensure_main_fragment(url: str) -> str:
    """Append `view=main` and `#main` for FMI pages so the main section is focused."""

    if "ilmatieteenlaitos.fi" not in url:
        return url

    split = urlsplit(url)
    params = dict(parse_qsl(split.query, keep_blank_values=True))
    params.setdefault("view", "main")
    query = urlencode(params, doseq=True)
    return urlunsplit((split.scheme, split.netloc, split.path, query, "main"))


def announcement_window_active(now: datetime | None = None) -> bool:
    """Return True between 14:00–17:00 Helsinki time."""

    now = now or datetime.now(TZ)
    return time(14, 0) <= now.time() < time(17, 0)


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


button_visible = announcement_window_active()
announcement_text = None
announcement_error = None

if button_visible:
    announcement_text, announcement_error = next_helsinki_departure_text()

if announcement_error:
    st.warning(announcement_error)

train_section_html = """
<div class="train-grid">
    <div class="train-card">
        <div class="embed-title">Ainola → Helsinki</div>
        <div class="embed-frame train-embed">
            <iframe src="https://junalahdot.fi/518952272?command=fs&id=219&dt=dep&lang=3&did=47&title=Ainola%20-%20Helsinki" loading="lazy" title="Ainola to Helsinki live departures" ></iframe>
        </div>
    </div>
    <div class="train-card">
        <div class="embed-title">Helsinki → Ainola</div>
        <div class="embed-frame train-embed">
            <iframe src="https://junalahdot.fi/518952272?command=fs&id=47&dt=dep&lang=3&did=219&title=Helsinki%20-%20Ainola" loading="lazy" title="Helsinki to Ainola live departures" ></iframe>
        </div>
    </div>
</div>
"""

announcement_ready = button_visible and announcement_text

if announcement_ready:
    header_html = """
    <div class="train-header">
        <button id="train-audio-btn" class="train-audio-btn" aria-label="Hear next Helsinki R-train">🚆</button>
        <span class="train-title">Live Train Departures</span>
    </div>
    """
else:
    header_html = """
    <div class="train-header">
        <span class="train-title-icon">🚆</span>
        <span class="train-title">Live Train Departures</span>
    </div>
    """

st.markdown(header_html, unsafe_allow_html=True)
st.markdown(train_section_html, unsafe_allow_html=True)

if announcement_ready:
    safe_text = json.dumps(announcement_text)
    st.markdown(
        f"""
        <script>
            (function() {{
                const text = {safe_text};

                const attachHandler = () => {{
                    const button = document.getElementById('train-audio-btn');
                    if (!button || !window.speechSynthesis) return false;

                    if (button.dataset.bound === 'true') return true;

                    const speak = () => {{
                        const utterance = new SpeechSynthesisUtterance(text);
                        try {{
                            const voices = window.speechSynthesis.getVoices();
                            if (voices && voices.length) {{
                                const preferredUk = voices.find(v => v.lang && v.lang.toLowerCase().startsWith('en-gb'));
                                const preferredEn = voices.find(v => v.lang && v.lang.toLowerCase().startsWith('en'));
                                utterance.voice = preferredUk || preferredEn || voices[0];
                            }}
                        }} catch (e) {{
                            // ignore voice selection errors
                        }}

                        window.speechSynthesis.cancel();
                        window.speechSynthesis.speak(utterance);
                    }};

                    // Warm up voices on iOS/Safari; required for some devices
                    if (typeof window.webkitSpeechSynthesis !== 'undefined') {{
                        window.speechSynthesis.getVoices();
                    }}

                    button.dataset.bound = 'true';
                    button.addEventListener('click', speak);
                    return true;
                }};

                const bound = attachHandler();
                if (bound) return;

                const onReady = () => {{
                    if (attachHandler()) {{
                        document.removeEventListener('readystatechange', onReady);
                        window.removeEventListener('load', onReady);
                    }}
                }};

                document.addEventListener('readystatechange', onReady);
                window.addEventListener('load', onReady);

                const observer = new MutationObserver(() => {{
                    if (attachHandler()) {{
                        observer.disconnect();
                    }}
                }});

                observer.observe(document.body, {{ childList: true, subtree: true }});
            }})();
        </script>
        """,
        unsafe_allow_html=True,
    )


helsinki_time = datetime.now(TZ).time()
if time(6, 0) <= helsinki_time < time(14, 0):
    st.markdown(
        """
        <div class="embed-wrapper" style="max-width: 480px; margin: left;">
        <div class="embed-title" style="font-weight:600; margin-bottom:6px; text-align:left;">
            Live R-Train Map (morning peak)
        </div>
        <div class="embed-frame" 
            style="
                position: relative;
                padding-bottom: 75%; /* keeps aspect ratio */
                height: 0;
                overflow: hidden;
                border-radius: 10px;
                box-shadow: 0 2px 6px rgba(0,0,0,0.2);
            ">
            <iframe 
            src="https://14142.net/kartalla/index.en.html?data=hsl&lat=60.475&lng=25.1&zoom=13&types=train&routes=R"
            title="Live Train Map"
            loading="lazy"
            style="
                position: absolute;
                top: 0; left: 0;
                width: 100%; height: 100%;
                border: none;
            ">
            </iframe>
        </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# Commute weather check (rain + cold)
needs_attention, commute_icon, commute_details = weather.rough_weather_check()

if needs_attention:
    st.markdown(f"### {commute_icon} Commute weather alert")
    st.markdown(f"{commute_details}")


embeds: List[Tuple[str, str, int, bool]] = [
    (
        "Paippinen Local Weather",
        "https://en.ilmatieteenlaitos.fi/local-weather/sipoo/paippinen",
        900,
        True,
    ),
    (
        "Traffic Situation Map",
        # Finnish Transport Infrastructure Agency, 4=road condidtions, 8=winter maintenance, 10=traffic flow
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
    resolved_url = ensure_main_fragment(url)
    frame_classes = "embed-frame"
    if narrow:
        frame_classes += " narrow-frame"
    st.markdown(
        f"""
        <div class="embed-wrapper">
            <div class="embed-title">{title}</div>
            <div class="{frame_classes}" style="height: {height}px;">
                <iframe src="{resolved_url}" loading="lazy" title="{title}"></iframe>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
st.title("😂 Misc")
# joke_official_api.py
# joke_and_quiz.py
import requests
import html  # used to unescape HTML entities from the trivia API

# ---------------------------
# 1️⃣  Random Joke (no API key)
# ---------------------------
url_joke = "https://official-joke-api.appspot.com/random_joke"

try:
    r = requests.get(url_joke, timeout=10)
    r.raise_for_status()
    joke = r.json()
    st.subheader("💬 Joke of the Day")
    st.markdown(f"**{joke['setup']}**  \n{joke['punchline']}")
except Exception as e:
    st.error(f"Could not fetch a joke: {e}")


# ============================================================
# 🎬 Movie Spotlight
# ============================================================

movie_spotlight()
