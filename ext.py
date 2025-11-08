"""ext.py

Standalone Streamlit page with embedded external resources.
"""

import streamlit as st
from streamlit.components.v1 import iframe

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
        }
        .embed-wrapper {
            margin-bottom: 1.2rem;
        }
    </style>
    """,
    unsafe_allow_html=True,
)

st.subheader("🚆 Live Train Departures")
train_left, train_right = st.columns(2, gap="medium")
with train_left:
    st.markdown("**Ainola → Helsinki**")
    with st.container():
        st.markdown('<div class="embed-frame">', unsafe_allow_html=True)
        iframe(
            "https://junalahdot.fi/518952272?command=fs&id=219&dt=dep&lang=3&did=47&title=Ainola%20-%20Helsinki",
            height=520,
        )
        st.markdown("</div>", unsafe_allow_html=True)
with train_right:
    st.markdown("**Helsinki → Ainola**")
    with st.container():
        st.markdown('<div class="embed-frame">', unsafe_allow_html=True)
        iframe(
            "https://junalahdot.fi/518952272?command=fs&id=47&dt=dep&lang=3&did=219&title=Helsinki%20-%20Ainola",
            height=520,
        )
        st.markdown("</div>", unsafe_allow_html=True)

st.subheader("🌦️ Weather & Conditions")
embeds = [
    ("Paippinen Local Weather", "https://en.ilmatieteenlaitos.fi/local-weather/sipoo/paippinen", 900),
    ("Weather Warnings", "https://en.ilmatieteenlaitos.fi/warnings", 900),
    (
        "Traffic Situation Map",
        "https://liikennetilanne.fintraffic.fi/kartta/?x=3010000&y=9720000&z=5&checkedLayers=3,10",
        900,
    ),
    (
        "Aurora & Space Weather (Nurmijärvi)",
        "https://www.ilmatieteenlaitos.fi/revontulet-ja-avaruussaa?station=NUR",
        900,
    ),
]

for title, url, height in embeds:
    st.markdown(f"**{title}**")
    st.markdown('<div class="embed-wrapper embed-frame">', unsafe_allow_html=True)
    iframe(url, height=height)
    st.markdown("</div>", unsafe_allow_html=True)
