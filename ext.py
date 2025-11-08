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
        }
        .train-card {
            flex: 1 1 420px;
            min-width: 280px;
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
        "https://liikennetilanne.fintraffic.fi/kartta/?lang=en&x=2791520.149538346&y=8496829.188520921&z=11&checkedLayers=1,3,10,11&basemap=streets-vector&iframe=true",
        720,
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
