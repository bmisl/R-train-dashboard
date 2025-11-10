"""ext.py

Standalone Streamlit page with embedded external resources.
"""

from typing import List, Tuple
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import streamlit as st

st.set_page_config(
    page_title="Commute Dashboard – My Commute",
    page_icon="🌐",
    layout="wide",
)

st.title("🌐 My Commute")

st.markdown(
    """
    <style>
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
            max-width: 1000px;
            margin: 0 auto;
        }
        @media (max-width: 900px) {
            .train-grid {
                flex-direction: column;
            }
            .train-card {
                flex: 1 1 auto;
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


st.subheader("🚆 Live Train Departures")
train_section_html = """
<div class="train-grid">
    <div class="train-card">
        <div class="embed-title">Ainola → Helsinki</div>
        <div class="embed-frame train-embed">
            <iframe
                src="https://junalahdot.fi/518952272?command=fs&id=219&dt=dep&lang=3&did=47&title=Ainola%20-%20Helsinki"
                loading="lazy"
                title="Ainola to Helsinki live departures"
            ></iframe>
        </div>
    </div>
    <div class="train-card">
        <div class="embed-title">Helsinki → Ainola</div>
        <div class="embed-frame train-embed">
            <iframe
                src="https://junalahdot.fi/518952272?command=fs&id=47&dt=dep&lang=3&did=219&title=Helsinki%20-%20Ainola"
                loading="lazy"
                title="Helsinki to Ainola live departures"
            ></iframe>
        </div>
    </div>
</div>
"""
st.markdown(train_section_html, unsafe_allow_html=True)

st.subheader("🌦️ Weather & Conditions")
embeds: List[Tuple[str, str, int, bool]] = [
    (
        "Paippinen Local Weather",
        "https://en.ilmatieteenlaitos.fi/local-weather/sipoo/paippinen",
        900,
        True,
    ),
    (
        "Weather Warnings",
        "https://en.ilmatieteenlaitos.fi/warnings",
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

# ---------------------------
# 2️⃣  Trivia Questions (3 medium true/false)
# ---------------------------
st.subheader("🧠 Quick Trivia")

url_trivia = "https://opentdb.com/api.php?amount=3&difficulty=medium&type=boolean"

try:
    r = requests.get(url_trivia, timeout=10)
    r.raise_for_status()
    data = r.json()
    questions = data["results"]

    for i, q in enumerate(questions, start=1):
        question = html.unescape(q["question"])
        correct = q["correct_answer"]
        with st.expander(f"Question {i}: {question}"):
            st.write(f"**Answer:** {correct}")
except Exception as e:
    st.error(f"Could not fetch trivia: {e}")


    # movie_snippet.py
st.title("🎬 Movie Spotlight")

url = "https://www.omdbapi.com/?i=tt3896198&apikey=8f375814"
r = requests.get(url)
movie = r.json()

# Short info
title = movie["Title"]
year = movie["Year"]
rating = movie["imdbRating"]
genre = movie["Genre"]
plot = movie["Plot"]
poster = movie["Poster"]

st.image(poster, width=180)
st.markdown(f"**{title} ({year})**  ⭐ {rating}")
st.caption(genre)
st.write(plot)

