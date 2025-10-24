import streamlit as st
import requests
from datetime import datetime, timedelta, timezone, time as dtime

# ===== Streamlit page settings =====
st.set_page_config(
    page_title="R-trains Ainola ↔ Helsinki",
    page_icon="🚆",
    layout="wide"
)

# Auto-refresh every 30 seconds
try:
    from streamlit_autorefresh import st_autorefresh
    st_autorefresh(interval=30000, key="train-refresh")
except:
    pass

# ===== CSS for layout + highlight style =====
st.markdown("""
<style>
.block-container {
    max-width: 900px;
    margin: auto;
    padding-top: 1rem;
}
.row-widget.stHorizontal > div {
    flex: 1 !important;
}
.highlight {
    background-color: rgba(200,200,200,0.3);
    padding: 4px;
    border-radius: 5px;
}
</style>
""", unsafe_allow_html=True)

# ===== Constants =====
HKI = "HKI"
AIN = "AIN"
NEXT_COUNT = 5
HEADERS = {"Digitraffic-User": "Birgir-hain/1.0"}


# ===== Utility Functions =====
def helsinki_now():
    import zoneinfo
    return datetime.now(zoneinfo.ZoneInfo("Europe/Helsinki"))

def parse_time(ts):
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))

def format_hki(dt):
    return dt.astimezone(helsinki_now().tzinfo).strftime("%H:%M")

def fetch_station_window(station_code):
    url = (
        f"https://rata.digitraffic.fi/api/v1/live-trains/station/{station_code}"
        f"?departing_trains=100&minutes_before_departure=30&minutes_after_departure=480"
    )
    r = requests.get(url, headers=HEADERS, timeout=15)
    r.raise_for_status()
    return r.json()

def extract_best_time(row):
    sched = parse_time(row["scheduledTime"])
    actual = parse_time(row["actualTime"]) if row.get("actualTime") else None
    estimate = parse_time(row.get("liveEstimateTime")) if row.get("liveEstimateTime") else None

    if actual:
        delay = int((actual - sched).total_seconds() / 60)
        return f"{format_hki(sched)} → {format_hki(actual)} ({delay:+} min)", actual
    elif estimate:
        delay = int((estimate - sched).total_seconds() / 60)
        return f"{format_hki(sched)} → {format_hki(estimate)} ({delay:+} min)", estimate
    else:
        return f"{format_hki(sched)}", sched

def get_trains(origin, destination):
    trains = fetch_station_window(origin)
    now_utc = datetime.now(timezone.utc)
    results = []

    for train in trains:
        if train.get("commuterLineID") != "R":
            continue

        rows = train["timeTableRows"]
        dep = next((r for r in rows if r["stationShortCode"] == origin and r["type"] == "DEPARTURE"), None)
        arr = next((r for r in rows if r["stationShortCode"] == destination and r["type"] == "ARRIVAL"), None)
        if not dep or not arr:
            continue
        if rows.index(dep) >= rows.index(arr):
            continue

        sched_time = parse_time(dep["scheduledTime"])
        if sched_time < now_utc:
            continue  # Remove past trains

        text, best = extract_best_time(dep)
        platform = dep.get("commercialTrack", "—")
        results.append((sched_time, train["trainNumber"], text, best, platform, rows))

    return sorted(results, key=lambda x: x[0])[:NEXT_COUNT]


# ===== UI Header =====
st.title("🚆 Ainola & Helsinki R-trains (Live)")
now = helsinki_now().time()
focus_H_to_A = dtime(12, 0) <= now < dtime(17, 0)
focus_label = "Helsinki → Ainola" if focus_H_to_A else "Ainola → Helsinki"
st.caption(f"Focus (local time {helsinki_now().strftime('%H:%M')}): **{focus_label}**")

# ===== Fetch trains =====
trains_A_to_H = get_trains(AIN, HKI)
trains_H_to_A = get_trains(HKI, AIN)

# ===== Determine next train in active direction =====
active_trains = trains_H_to_A if focus_H_to_A else trains_A_to_H
next_train = None
now_utc = datetime.now(timezone.utc)

for sched, num, text, best_time, platform, rows in active_trains:
    if best_time >= now_utc:
        next_train = (num, text, platform, rows, sched)
        break

# ===== Display train lists =====
col1, col2 = st.columns(2)

def render_column(col, trains, title, is_active_column):
    if is_active_column:
        col.markdown(f"<h3 style='text-decoration: underline; font-weight:700;'>{title}</h3>", unsafe_allow_html=True)
    else:
        col.subheader(title)

    for sched, num, text, best_time, platform, rows in trains:
        if next_train and num == next_train[0] and is_active_column:
            col.markdown(
                f"<span style='background-color: rgba(200,200,200,0.3); "
                f"padding: 3px 4px; border-radius:4px; display:inline-block;'>"
                f"<b>Train {num}</b> — {text}"
                f"</span>",
                unsafe_allow_html=True
            )
        else:
            col.markdown(f"**Train {num}** — {text}")

# Left column = Ainola → Helsinki
render_column(col1, trains_A_to_H, "Ainola → Helsinki", not focus_H_to_A)

# Right column = Helsinki → Ainola
render_column(col2, trains_H_to_A, "Helsinki → Ainola", focus_H_to_A)

# ===== Detailed next train section =====
st.markdown("---")

if next_train:
    train_no, time_text, platform, rows, sched_time = next_train
    minutes_to_departure = int((sched_time - now_utc).total_seconds() / 60)
    final_dest = AIN if focus_H_to_A else HKI

    # Arrival info
    arr_row = next((r for r in rows if r["stationShortCode"] == final_dest and r["type"] == "ARRIVAL"), None)
    arrival_time = format_hki(parse_time(arr_row["scheduledTime"])) if arr_row else "—"
    arrival_track = arr_row.get("commercialTrack", "—") if arr_row else "—"

    st.subheader(f"⬇ Next train ({focus_label})")
    st.markdown(
        f"<span style='background-color: rgba(200,200,200,0.3); "
        f"padding:6px 8px; border-radius:6px; display:inline-block;'>"
        f"<b>Train {train_no}</b> | Departs: {time_text} <i>(in {minutes_to_departure} min)</i> | Platform: {platform}"
        f"</span>",
        unsafe_allow_html=True
    )

    st.write(f"Arrives at {final_dest}: {arrival_time} | Track: {arrival_track}")
else:
    st.info("No upcoming trains in this direction.")
