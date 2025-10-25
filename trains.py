import requests
from datetime import datetime, timedelta, timezone
import zoneinfo
import streamlit as st

@st.cache_data(ttl=30)  # Refresh every 30 seconds
def get_trains_cached(origin, destination):
    return get_trains(origin, destination)


# ----------------------------
# CONSTANTS
# ----------------------------
TZ = zoneinfo.ZoneInfo("Europe/Helsinki")
HEADERS = {"Digitraffic-User": "Birgir-ainola-dashboard/1.0"}
PAST_MINUTES = 0
NEXT_COUNT = 5

# ----------------------------
# STATION NAMES
# ----------------------------
CUSTOM_STATION_NAMES = {
    "HKI": "Helsinki",
    "PSL": "Pasila",
    "TKL": "Tikkurila",
    "KE": "Kerava",
    "AIN": "Ainola",
    "JP": "Järvenpää",
    "SAU": "Saunakallio",
    "JK": "Jokela",
    "HY": "Hyvinkää",
    "RI": "Riihimäki",
    "TPE": "Tampere",
}

# ----------------------------
# TIME HELPERS
# ----------------------------
def parse_time(ts: str) -> datetime:
    """
    Convert ISO8601 string like '2024-01-26T12:05:00.000Z'
    into a timezone-aware datetime object (UTC).
    """
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))

def format_hki(dt: datetime) -> str:
    """Format a datetime to local Helsinki time as HH:MM."""
    return dt.astimezone(TZ).strftime("%H:%M")

# ----------------------------
# TRAIN FETCH FUNCTIONS
# ----------------------------
def fetch_station_window(station_code: str, before=0, after=360, limit=200):
    """
    Fetch trains for a specific station within a time window.
    """
    url = (
        f"https://rata.digitraffic.fi/api/v1/live-trains/station/{station_code}"
        f"?departing_trains={limit}&minutes_before_departure={before}&minutes_after_departure={after}"
    )
    r = requests.get(url, headers=HEADERS, timeout=12)
    r.raise_for_status()
    return r.json()

def extract_best_time(row):
    """
    Returns tuple (text, best_dt):
    text = formatted schedule + actual or estimate + delay
    best_dt = datetime of actual or estimate, used for comparisons
    """
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

def get_trains(origin: str, destination: str):
    """
    Returns the next R trains from origin to destination:
    [
        (sched_time, trainNumber, time_text, best_dt, platform, rows)
    ]
    """
    trains = fetch_station_window(origin)
    now_utc = datetime.now(timezone.utc)
    results = []

    for tr in trains:
        if tr.get("commuterLineID") != "R":
            continue

        rows = tr["timeTableRows"]
        dep = next((r for r in rows if r["stationShortCode"] == origin and r["type"] == "DEPARTURE"), None)
        arr = next((r for r in rows if r["stationShortCode"] == destination and r["type"] == "ARRIVAL"), None)
        if not dep or not arr:
            continue
        if rows.index(dep) >= rows.index(arr):
            continue

        sched_time = parse_time(dep["scheduledTime"])
        if sched_time < now_utc - timedelta(minutes=PAST_MINUTES):
            continue

        text, best = extract_best_time(dep)
        platform = dep.get("commercialTrack", "—")
        results.append((sched_time, tr["trainNumber"], text, best, platform, rows))

    return sorted(results, key=lambda x: x[0])[:NEXT_COUNT]

# ----------------------------
# DESTINATION NAME HELPERS
# ----------------------------
def fetch_station_names():
    """
    Returns dict {stationShortCode: human name}
    """
    url = "https://rata.digitraffic.fi/api/v1/metadata/stations"
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        r.raise_for_status()
        stations = r.json()

        name_map = {}
        for s in stations:
            code = s["stationShortCode"]
            name = s.get("stationName", s["stationShortCode"])

            # Apply our preferred naming, if exists
            if code in CUSTOM_STATION_NAMES:
                name = CUSTOM_STATION_NAMES[code]

            name_map[code] = name

        return name_map

    except Exception:
        # Fallback to custom station names only
        return CUSTOM_STATION_NAMES.copy()


def final_destination_name(rows, station_names: dict) -> str:
    """
    Find the final station of this train based on timetable rows.
    Then convert station code -> human name using station_names dict.
    """
    final_row = next((r for r in reversed(rows) if r.get("type") == "ARRIVAL"), rows[-1])
    code = final_row.get("stationShortCode", "—")
    return station_names.get(code, code)

# ----------------------------
# PRESENTATION HELPERS
# ----------------------------
def heading_md(title: str, active: bool) -> str:
    """
    Return a markdown heading for a train column.
    Active headings are underlined and bold; inactive are bold only.
    """
    if active:
        return f"### **<u>{title}</u>**"
    return f"### **{title}**"

if __name__ == "__main__":
    # Human-friendly terminal test
    print("Fetching next R-trains from Ainola → Helsinki:\n")

    station_names = fetch_station_names()
    trains = get_trains("AIN", "HKI")

    if not trains:
        print("No trains found.")
    else:
        for sched_time, num, text, best_dt, platform, rows in trains:
            dest_name = final_destination_name(rows, station_names)
            print(f"→ To {dest_name} (R {num})")
            print(f"  Departs: {text}")
            print(f"  Platform: {platform}")
            print()