"""ext.py

Standalone Streamlit page with embedded external resources.
"""

from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import streamlit as st

st.set_page_config(
    page_title="Commute Dashboard – External Resources",
    page_icon="🌐",
    layout="wide",
)

st.title("🌐 External Resources")

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
            height: 520px;
            position: relative;
        }
        .train-embed iframe {
            width: 303%;
            height: 1560px;
            transform: scale(0.33);
            transform-origin: top left;
        }
        @media (max-width: 900px) {
            .train-grid {
                flex-direction: column;
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
embeds = [
    ("Paippinen Local Weather", "https://en.ilmatieteenlaitos.fi/local-weather/sipoo/paippinen", 900),
    ("Weather Warnings", "https://en.ilmatieteenlaitos.fi/warnings", 900),
    (
        "Traffic Situation Map",
        "https://liikennetilanne.fintraffic.fi/kartta/?x=3010000&y=9720000&z=5&checkedLayers=3,10",
        0,
    ),
    (
        "Aurora & Space Weather (Nurmijärvi)",
        "https://www.ilmatieteenlaitos.fi/revontulet-ja-avaruussaa?station=NUR",
        900,
    ),
]

for title, url, height in embeds:
    if title == "Traffic Situation Map":
        st.markdown(
            f"""
            <div class="embed-wrapper">
                <div class="embed-title">{title}</div>
                <div class="embed-frame" style="padding: 1.5rem; display: flex; flex-direction: column; gap: 0.75rem;">
                    <div>This interactive map requires accepting cookies on the provider's site.</div>
                    <a href="{url}" target="_blank" rel="noopener" style="align-self: flex-start; background: #0f766e; color: #ffffff; padding: 0.5rem 0.9rem; border-radius: 0.5rem; text-decoration: none; font-weight: 600;">Open traffic map in a new tab ↗</a>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        continue

    resolved_url = ensure_main_fragment(url)
    st.markdown(
        f"""
        <div class="embed-wrapper">
            <div class="embed-title">{title}</div>
            <div class="embed-frame" style="height: {height}px;">
                <iframe src="{resolved_url}" loading="lazy" title="{title}"></iframe>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
