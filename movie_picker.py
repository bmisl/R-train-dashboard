# movie_picker.py
# Streamlit TMDb movie browser — clean, fast, stable toolbar (no spinners)

import random
import requests
import streamlit as st

# -----------------------------
# Config / constants
# -----------------------------
TMDB_API_KEY = st.secrets["TMDB_API_KEY"]
TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p/w500"
PLACEHOLDER_POSTER = "https://via.placeholder.com/180x270.png?text=No+Poster"

# -----------------------------
# Caching helpers
# -----------------------------
@st.cache_data(ttl=3600)
def tmdb_discover(params: dict) -> list:
    base = "https://api.themoviedb.org/3/discover/movie"
    default = {
        "api_key": TMDB_API_KEY,
        "language": "en-US",
        "include_adult": "false",
        "include_video": "false",
        "sort_by": "popularity.desc",
        "page": 1,
        "vote_count.gte": 50,
    }
    merged = {**default, **params}
    r = requests.get(base, params=merged, timeout=10).json()
    return r.get("results", [])

def _get_multi_page(params: dict, pages: int = 3) -> list:
    out = []
    for p in range(1, pages + 1):
        batch = tmdb_discover({**params, "page": p})
        if not batch:
            break
        out.extend(batch)
    return out

@st.cache_data(ttl=3600)
def get_tmdb_details(movie_id: int) -> dict:
    url = f"https://api.themoviedb.org/3/movie/{movie_id}"
    r = requests.get(url, params={"api_key": TMDB_API_KEY, "language": "en-US"}, timeout=10)
    return r.json()

@st.cache_data(ttl=3600)
def get_tmdb_credits(movie_id: int) -> dict:
    url = f"https://api.themoviedb.org/3/movie/{movie_id}/credits"
    r = requests.get(url, params={"api_key": TMDB_API_KEY, "language": "en-US"}, timeout=10)
    return r.json()

@st.cache_data(ttl=3600)
def tmdb_most_recent(vote_count_min: int = 50) -> dict | None:
    results = tmdb_discover({
        "sort_by": "primary_release_date.desc",
        "vote_count.gte": vote_count_min,
        "page": 1,
    })
    return results[0] if results else None

# -----------------------------
# Discover helpers (relative)
# -----------------------------
def discover_more_popular_than(current_pop: float, exclude_id: int | None = None) -> list:
    results = _get_multi_page({
        "popularity.gte": current_pop + 0.1,
        "sort_by": "popularity.desc",
        "vote_count.gte": 100,
    }, pages=3)
    return [m for m in results if m.get("id") != exclude_id and float(m.get("popularity", 0)) > current_pop]

def discover_older_within_2y(current_year: int, exclude_id: int | None = None) -> list:
    start = f"{max(1870, current_year-2)}-01-01"
    end   = f"{max(1870, current_year-1)}-12-31"
    results = _get_multi_page({
        "primary_release_date.gte": start,
        "primary_release_date.lte": end,
    }, pages=3)
    return [m for m in results if m.get("id") != exclude_id]

def discover_newer_within_2y(current_year: int, exclude_id: int | None = None) -> list:
    start = f"{current_year+1}-01-01"
    end   = f"{current_year+2}-12-31"
    results = _get_multi_page({
        "primary_release_date.gte": start,
        "primary_release_date.lte": end,
    }, pages=3)
    return [m for m in results if m.get("id") != exclude_id]

@st.cache_data(ttl=3600)
def discover_same_director_movies(person_id: int, exclude_id: int | None = None) -> list:
    """Strict: only films this person directed, sorted by popularity."""
    url = f"https://api.themoviedb.org/3/person/{person_id}/movie_credits"
    r = requests.get(url, params={"api_key": TMDB_API_KEY, "language": "en-US"}, timeout=10).json()
    directed = [m for m in r.get("crew", []) if m.get("job") == "Director" and m.get("id") != exclude_id]
    directed.sort(key=lambda x: x.get("popularity", 0), reverse=True)
    return directed

def discover_same_director(current_movie: dict) -> list:
    cur_id = current_movie.get("id")
    credits = get_tmdb_credits(cur_id)
    directors = [c for c in credits.get("crew", []) if c.get("job") == "Director"]
    if not directors:
        return []
    person_id = directors[0]["id"]
    return discover_same_director_movies(person_id, exclude_id=cur_id)

def discover_same_genre(current_movie: dict) -> list:
    cur_id = current_movie.get("id")
    gids = current_movie.get("genre_ids") or []
    if not gids:
        details = get_tmdb_details(cur_id)
        gids = [g["id"] for g in details.get("genres", [])]
    if not gids:
        return []
    results = _get_multi_page({
        "with_genres": str(gids[0]),
        "sort_by": "popularity.desc",
    }, pages=3)
    return [m for m in results if m.get("id") != cur_id]

# -----------------------------
# Presentation
# -----------------------------
def build_poster_url(poster_path: str | None) -> str:
    return f"{TMDB_IMAGE_BASE}{poster_path}" if poster_path else PLACEHOLDER_POSTER

def get_people_summary(movie_id: int) -> tuple[str, str, str]:
    details = get_tmdb_details(movie_id)
    credits = get_tmdb_credits(movie_id)
    director = ""
    for c in credits.get("crew", []):
        if c.get("job") == "Director":
            director = c.get("name", "")
            break
    cast = ", ".join([p["name"] for p in credits.get("cast", [])[:5]])
    genres = ", ".join([g["name"] for g in details.get("genres", [])])
    return director, cast, genres

def render_movie_card(placeholder: st.delta_generator.DeltaGenerator, movie: dict | None):
    if not movie:
        return
    st.session_state.current_movie = movie
    title = movie.get("title", "Unknown")
    release = movie.get("release_date") or ""
    year = release[:4] if release else "–"
    overview = movie.get("overview", "No plot summary available.")
    popularity = float(movie.get("popularity", 0.0))
    vote_avg = float(movie.get("vote_average", 0.0))
    poster = build_poster_url(movie.get("poster_path"))
    director, cast, genres = get_people_summary(movie.get("id"))

    with placeholder.container():
        col1, col2 = st.columns([1, 2])
        with col1:
            st.image(poster, width=180)
        with col2:
            st.markdown(f"**{title} ({year})**  ⭐ {vote_avg:.1f} / 10")
            if director:
                st.caption(f"🎬 Directed by **{director}**")
            if genres:
                st.caption(f"🎭 {genres}")
            if cast:
                st.caption(f"👥 {cast}")
            st.caption(f"🔥 Popularity: {popularity:.0f}")
            st.write(overview)

# -----------------------------
# App
# -----------------------------
def main():
    st.title("🎬 Movie Spotlight")

    # Hide Streamlit's "Running..." spinner and progress messages
    st.markdown(
        """
        <style>
        [data-testid="stStatusWidget"] {display: none !important;}
        [data-testid="stSpinner"] {display: none !important;}
        div.stNotification {display: none !important;}
        </style>
        """,
        unsafe_allow_html=True
    )


    # Optional: hide Streamlit's "Running..." indicator
    st.markdown(
        "<style>[data-testid='stStatusWidget']{display:none !important;}</style>",
        unsafe_allow_html=True,
    )

    # Keep a persistent placeholder for the movie card (prevents any layout jump)
    card_placeholder = st.empty()

    # --- Toolbar (buttons always on screen) ---
    cols = st.columns(6)
    btn_random   = cols[0].button("🎲 Random", key="btn_random")
    btn_popular  = cols[1].button("🔥 More popular", key="btn_more_popular")
    btn_older    = cols[2].button("⏳ Older (−2y)", key="btn_older")
    btn_newer    = cols[3].button("🚀 Newer (+2y)", key="btn_newer")
    btn_director = cols[4].button("🎬 Same director", key="btn_same_director")
    btn_genre    = cols[5].button("🎭 Same genre", key="btn_same_genre")

    # --- Persistent movie container ---
    if "movie_placeholder" not in st.session_state:
        st.session_state.movie_placeholder = st.empty()

    movie_container = st.session_state.movie_placeholder

    # Always render the last known movie (even during rerun)
    current_movie = st.session_state.get("current_movie")
    if current_movie:
        render_movie_card(movie_container, current_movie)
    else:
        # Reserve fixed space before any movie has loaded
        movie_container.markdown("<div style='min-height:420px'></div>", unsafe_allow_html=True)

    # Seed current movie once
    if "current_movie" not in st.session_state:
        seed = tmdb_discover({
            "primary_release_date.gte": "2022-01-01",
            "vote_count.gte": 100,
        })
        st.session_state.current_movie = random.choice(seed) if seed else tmdb_most_recent()

    selected = None
    cur = st.session_state.get("current_movie")

    # Decide action (no UI calls here; just compute)
    if btn_random:
        pool = _get_multi_page({
            "primary_release_date.gte": "2022-01-01",
            "vote_count.gte": 100,
        }, pages=3)
        if pool:
            selected = random.choice(pool)
            

    elif btn_popular and cur:
        cur_pop = float(cur.get("popularity", 0.0))
        pool = discover_more_popular_than(cur_pop, exclude_id=cur.get("id"))
        if pool:
            selected = random.choice(pool)

    elif btn_older and cur:
        y = int((cur.get("release_date") or "0000")[:4] or 0)
        pool = discover_older_within_2y(y, exclude_id=cur.get("id"))
        if pool:
            selected = random.choice(pool)

    elif btn_newer and cur:
        y = int((cur.get("release_date") or "0000")[:4] or 0)
        pool = discover_newer_within_2y(y, exclude_id=cur.get("id"))
        if pool:
            selected = random.choice(pool)
        else:
            fallback = tmdb_most_recent(vote_count_min=50)
            if fallback:
                selected = fallback

    elif btn_director and cur:
        pool = discover_same_director(cur)
        if pool:
            selected = random.choice(pool)

    elif btn_genre and cur:
        pool = discover_same_genre(cur)
        if pool:
            selected = random.choice(pool)

    if selected:
        st.session_state.current_movie = selected
        render_movie_card(movie_container, selected)

if __name__ == "__main__":
    main()

# movie_picker.py

def movie_spotlight():
    """Embeddable Streamlit widget for Movie Spotlight."""
    import streamlit as st
    import random

    # Hide Streamlit's "Running..." spinner and messages
    st.markdown(
        """
        <style>
        [data-testid="stStatusWidget"] {display:none !important;}
        [data-testid="stSpinner"] {display:none !important;}
        div.stNotification {display:none !important;}
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("## 🎬 Movie Spotlight")

    # --- Toolbar buttons ---
    cols = st.columns(6)
    btn_random   = cols[0].button("🎲 Random", key="btn_random")
    btn_popular  = cols[1].button("🔥 More popular", key="btn_more_popular")
    btn_older    = cols[2].button("⏳ Older (−2y)", key="btn_older")
    btn_newer    = cols[3].button("🚀 Newer (+2y)", key="btn_newer")
    btn_director = cols[4].button("🎬 Same director", key="btn_same_director")
    btn_genre    = cols[5].button("🎭 Same genre", key="btn_same_genre")

    # --- Persistent placeholder for the movie card ---
    if "movie_placeholder" not in st.session_state:
        st.session_state.movie_placeholder = st.empty()
    movie_container = st.session_state.movie_placeholder

    # Always render last known movie (prevents jump)
    current_movie = st.session_state.get("current_movie")
    if current_movie:
        render_movie_card(movie_container, current_movie)
    else:
        movie_container.markdown("<div style='min-height:420px'></div>", unsafe_allow_html=True)

    # --- Button actions ---
    selected = None
    cur = st.session_state.get("current_movie")

    if btn_random:
        pool = _get_multi_page({
            "primary_release_date.gte": "2022-01-01",
            "vote_count.gte": 100,
        }, pages=3)
        if pool:
            selected = random.choice(pool)

    elif btn_popular and cur:
        cur_pop = float(cur.get("popularity", 0.0))
        pool = discover_more_popular_than(cur_pop, exclude_id=cur.get("id"))
        if pool:
            selected = random.choice(pool)

    elif btn_older and cur:
        y = int((cur.get("release_date") or "0000")[:4] or 0)
        pool = discover_older_within_2y(y, exclude_id=cur.get("id"))
        if pool:
            selected = random.choice(pool)

    elif btn_newer and cur:
        y = int((cur.get("release_date") or "0000")[:4] or 0)
        pool = discover_newer_within_2y(y, exclude_id=cur.get("id"))
        if pool:
            selected = random.choice(pool)
        else:
            fallback = tmdb_most_recent(vote_count_min=50)
            if fallback:
                selected = fallback

    elif btn_director and cur:
        pool = discover_same_director(cur)
        if pool:
            selected = random.choice(pool)

    elif btn_genre and cur:
        pool = discover_same_genre(cur)
        if pool:
            selected = random.choice(pool)

    # --- Update the visible movie if needed ---
    if selected:
        st.session_state.current_movie = selected
        render_movie_card(movie_container, selected)
