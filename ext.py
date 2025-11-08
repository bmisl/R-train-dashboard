"""ext.py

Standalone Streamlit page with embedded external resources.
"""

from datetime import date
import hashlib
import json
import re
from html import unescape
from typing import Iterable, List, Optional, Tuple
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import requests
import streamlit as st

st.set_page_config(
    page_title="Commute Dashboard – External Resources",
    page_icon="🌐",
    layout="wide",
)

st.title("🌐 External Resources")


def _collect_quotes(node: object, seen: Optional[set] = None) -> List[Tuple[str, Optional[str]]]:
    """Recursively collect quote/author tuples from a nested structure."""

    if seen is None:
        seen = set()

    collected: List[Tuple[str, Optional[str]]] = []

    if isinstance(node, dict):
        maybe_quote = node.get("quote")
        if isinstance(maybe_quote, str):
            text = maybe_quote.strip()
            if text and text not in seen:
                seen.add(text)
                author = node.get("author") or node.get("writer") or node.get("source")
                if isinstance(author, str):
                    author = author.strip() or None
                else:
                    author = None
                collected.append((text, author))
        for value in node.values():
            collected.extend(_collect_quotes(value, seen))
    elif isinstance(node, list):
        for item in node:
            collected.extend(_collect_quotes(item, seen))

    return collected


@st.cache_data(show_spinner=False, ttl=60 * 60 * 6)
def _load_kevin_kelly_quotes() -> List[Tuple[str, Optional[str]]]:
    """Fetch and parse quotes from Glasp."""

    url = "https://glasp.co/quotes/kevin-kelly"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
    except requests.RequestException:
        return []

    text = response.text

    quotes: List[Tuple[str, Optional[str]]] = []

    # Attempt to parse Nuxt state payload which contains structured quote data.
    nuxt_match = re.search(r"window\.__NUXT__=(.*?);\s*</script>", text, re.DOTALL)
    if nuxt_match:
        payload = nuxt_match.group(1)
        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            data = None
        if data is not None:
            quotes.extend(_collect_quotes(data))

    if not quotes:
        # Fallback: parse rendered quote blocks from the HTML markup.
        block_re = re.compile(
            r'<div[^>]+class="[^"}]*relative\s+my-10[^"}]*"[^>]*>(.*?)<div class="border',
            re.DOTALL,
        )
        text_re = re.compile(
            r'<div[^>]+class="[^"}]*text-lg[^"}]*text-gray-700[^"}]*"[^>]*>(.*?)</div>',
            re.DOTALL,
        )
        author_re = re.compile(
            r'<div[^>]+class="[^"}]*text-lg[^"}]*"[^>]*>\s*[—-]\s*(.*?)</div>',
            re.DOTALL,
        )

        for block in block_re.finditer(text):
            block_html = block.group(1)
            text_match = text_re.search(block_html)
            if not text_match:
                continue
            raw_quote = re.sub(r"<.*?>", "", text_match.group(1))
            cleaned_quote = unescape(re.sub(r"\s+", " ", raw_quote)).strip()
            cleaned_quote = cleaned_quote.strip('"“”')
            if not cleaned_quote:
                continue
            author_match = author_re.search(block_html)
            author = None
            if author_match:
                raw_author = re.sub(r"<.*?>", "", author_match.group(1))
                author = unescape(re.sub(r"\s+", " ", raw_author)).strip()
            quotes.append((cleaned_quote, author or "Kevin Kelly"))

    if not quotes:
        # Final fallback: look for JSON-like quote fragments in the markup.
        for match in re.finditer(r'"quote"\s*:\s*"(.*?)"', text):
            snippet = match.group(1)
            try:
                snippet = bytes(snippet, "utf-8").decode("unicode_escape")
            except Exception:
                pass
            cleaned = re.sub(r"\s+", " ", snippet).strip()
            if cleaned:
                quotes.append((cleaned.strip('"“”'), "Kevin Kelly"))

    # Remove duplicates while preserving order.
    deduped: List[Tuple[str, Optional[str]]] = []
    seen_quotes = set()
    for quote_text, author in quotes:
        key = quote_text.strip()
        if not key or key in seen_quotes:
            continue
        seen_quotes.add(key)
        deduped.append((quote_text.strip(), author))

    return deduped


def _select_quote(quotes: Iterable[Tuple[str, Optional[str]]]) -> Optional[Tuple[str, Optional[str]]]:
    quotes = list(quotes)
    if not quotes:
        return None

    today = date.today().isoformat().encode("utf-8")
    digest = hashlib.sha256(today).hexdigest()
    index = int(digest, 16) % len(quotes)
    return quotes[index]


quotes = _load_kevin_kelly_quotes()
selected_quote = _select_quote(quotes)

if selected_quote is None:
    st.info("Daily quote unavailable right now. Please try again later.")
else:
    quote_text, quote_author = selected_quote
    attribution = f"— {quote_author}" if quote_author else ""
    st.markdown(
        f"""
        <div class="embed-frame" style="padding: 1.2rem; margin-bottom: 1.2rem;">
            <div style="font-size: 1.05rem; font-weight: 500; margin-bottom: 0.4rem;">Quote of the Day</div>
            <div style="font-style: italic; font-size: 1.05rem;">“{quote_text}”</div>
            <div style="margin-top: 0.4rem; font-size: 0.95rem;">{attribution}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

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
