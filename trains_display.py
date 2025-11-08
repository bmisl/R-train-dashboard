"""
trains_display.py
-----------------
UI-neutral display for R-line trains.

- Uses trains.py (get_trains, load_config)
- Returns HTML (no Streamlit imports)
- Focus column (morning: Ainola→Helsinki, afternoon: Helsinki→Ainola)
  gets a light grey text-tight highlight on the next train.
- Both columns: next train shows a second line with platform + "departs in X min".
- Non-next trains: single line, not bold.
- Added: Typical commute trains section at bottom
"""

from datetime import datetime, time as dtime, timezone, timedelta
from io import StringIO
import zoneinfo

from trains import get_trains, load_config


# ----------------------------
# 1) CONFIG
# ----------------------------
cfg = load_config()
STATIONS = cfg.get("STATIONS", {})
HOME_STATIONS = cfg.get("HOME_STATIONS", {"origin": "AIN", "destination": "HKI"})
TRAIN_LINE = cfg.get("TRAIN_LINE", "R")

ORIGIN = HOME_STATIONS.get("origin", "AIN")
DEST   = HOME_STATIONS.get("destination", "HKI")

TZ = zoneinfo.ZoneInfo("Europe/Helsinki")

# ----------------------------
# 2) HELPERS
# ----------------------------
def enrich_and_filter(tr_list):
    """
    Filter past trains and compute minutes to departure.
    Input from trains.get_trains():
      (sched_time, trainNumber, time_text, best_dt, platform, rows)
    Output:
      (sched_time, num, text, best_dt, platform, rows, mins_until)
    """
    now_utc = datetime.now(timezone.utc)
    future = []
    for sched_time, num, text, best_dt, platform, rows in tr_list:
        best_dt = best_dt or sched_time
        mins = int((best_dt - now_utc).total_seconds() / 60)
        if mins >= 0:
            future.append((sched_time, num, text, best_dt, platform, rows, mins))
    future.sort(key=lambda t: t[3])  # by best_dt
    return future[:5]

def filter_by_time(tr_list, target_hour, target_minute):
    """
    Filter trains to those departing at or after target time.
    Handles next-day wrapping if target time has passed.
    Returns list of (sched_time, num, text, best_dt, platform, rows).
    """
    now_hki = datetime.now(TZ)
    target_time = now_hki.replace(hour=target_hour, minute=target_minute, second=0, microsecond=0)
    
    # If target time has passed today, look for tomorrow
    if target_time <= now_hki:
        target_time = target_time + timedelta(days=1)
    
    target_utc = target_time.astimezone(timezone.utc)
    
    filtered = [(st, num, text, bdt, plat, rows) 
                for st, num, text, bdt, plat, rows in tr_list 
                if st >= target_utc]
    return filtered[:5]

def active_direction_now():
    """
    Morning emphasis (Ainola→Helsinki) until 12:00.
    Afternoon emphasis (Helsinki→Ainola) 12:00–18:30.
    Returns (active_left, active_right).
    """
    now_local = datetime.now(TZ).time()
    focus_return = dtime(12, 0) <= now_local < dtime(18, 30)
    return (not focus_return, focus_return)

def format_row(dest_name, num, text, platform, mins_until=None,
               show_details=False, highlight_bg=False, bold_only=False):
    """
    Render a single train row:
      - main line: To <Dest> (R <num>) – formatted time text
        (from trains.py, e.g. "14:21 → 14:26 (+5 min)" or "14:21")
      - details line (optional): Platform X • departs in N min
      - highlight_bg: focus column's first train → grey box wraps both lines
      - bold_only: inactive column's first train → bold main line only
    """
    main_text = f"To {dest_name} ({TRAIN_LINE} {num}) — {text}"

    details = ""
    if show_details:
        platform_text = f"Platform {platform}"
        if mins_until is not None:
            platform_text += f" • departs in {mins_until} min"
        details = (
            "<br><span style='font-size:13px; opacity:0.8;'>"
            f"{platform_text}"
            "</span>"
        )

    # Case 1: highlighted (focus column)
    if highlight_bg:
        return (
            "<div style='margin-bottom:4px;'>"
            "<span style='background-color:#e9e9e9; border-radius:4px; padding:1px 6px; display:inline-block;'>"
            f"<b>{main_text}</b>"
            f"{details}"
            "</span>"
            "</div>"
        )

    # Case 2: inactive column's first train (bold main line only)
    elif bold_only:
        return (
            "<div style='margin-bottom:4px;'>"
            f"<b>{main_text}</b>"
            f"{details}"
            "</div>"
        )

    # Case 3: all other trains
    else:
        return (
            "<div style='margin-bottom:4px;'>"
            f"{main_text}"
            f"{details}"
            "</div>"
        )

# ----------------------------
# 3) RENDER
# ----------------------------
def render_trains_html():
    """
    Returns an HTML block with two sections:
    1. Current trains (two columns, time-based highlighting)
    2. Typical commute trains (two columns, fixed times: 07:00 and 15:00)
    """
    # Fetch and prepare current data
    to_city = enrich_and_filter(get_trains(ORIGIN, DEST))
    to_home = enrich_and_filter(get_trains(DEST, ORIGIN))

    origin_name = STATIONS.get(ORIGIN, ORIGIN)
    dest_name   = STATIONS.get(DEST, DEST)
    active_left, active_right = active_direction_now()

    html = StringIO()

    # --- Styling: compact, no margins, transparent background ---
    html.write("""
    <html>
    <head>
    <style>
        body {
            margin: 0;
            padding: 0;
            overflow: hidden;
            background: transparent;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto,
                         Oxygen, Ubuntu, Cantarell, 'Open Sans', 'Helvetica Neue', sans-serif;
        }
        h3 {
            margin-top: 0;
            margin-bottom: 2px;
        }
        h4 {
            margin-top: 0;
            margin-bottom: 4px;
        }
        div {
            margin-bottom: 2px;
        }
        hr {
            border: none;
            border-top: 1px solid #ccc;
            margin: 20px 0;
        }
        .train-columns {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
            gap: 20px;
            align-items: start;
        }
        .train-columns > div {
            min-width: 0;
        }
        @media (max-width: 520px) {
            .train-columns {
                gap: 12px;
            }
        }
    </style>
    </head>
    <body>
    """)

    # --- SECTION 1: CURRENT TRAINS ---
    html.write("<h3>Next trains</h3>")
    html.write("<div class='train-columns'>")

    # Left column (to city)
    html.write("<div>")
    html.write(f"<h4>{origin_name} → {dest_name}</h4>")
    if not to_city:
        html.write("<p><i>No upcoming trains.</i></p>")
    else:
        for i, (sc, num, text, best_dt, plat, rows, mins) in enumerate(to_city):
            html.write(
                format_row(
                    dest_name, num, text, plat, mins,
                    show_details=(i == 0),
                    highlight_bg=(i == 0 and active_left),
                    bold_only=(i == 0 and not active_left)
                )
            )
    html.write("</div>")  # end left column

    # Right column (to home)
    html.write("<div>")
    html.write(f"<h4>{dest_name} → {origin_name}</h4>")
    if not to_home:
        html.write("<p><i>No upcoming trains.</i></p>")
    else:
        for i, (sc, num, text, best_dt, plat, rows, mins) in enumerate(to_home):
            html.write(
                format_row(
                    origin_name, num, text, plat, mins,
                    show_details=(i == 0),
                    highlight_bg=(i == 0 and active_right),
                    bold_only=(i == 0 and not active_right)
                )
            )
    html.write("</div>")  # end right column
    html.write("</div>")  # end current trains section

    # --- HORIZONTAL SEPARATOR ---
    html.write("<hr>")

    # --- SECTION 2: TYPICAL COMMUTE TRAINS ---
    html.write("<h3>Typical commute trains</h3>")
    
    # Fetch typical commute trains with extended window
    from trains import fetch_station_window
    morning_trains_raw = fetch_station_window(ORIGIN, before=60, after=720, limit=500)
    evening_trains_raw = fetch_station_window(DEST, before=60, after=720, limit=500)
    
    # Process through get_trains logic
    from trains import TRAIN_LINE as cfg_line
    
    def process_trains_for_route(trains_raw, origin_code, dest_code):
        """Extract trains for specific route from raw API data."""
        results = []
        for tr in trains_raw:
            if tr.get("commuterLineID") != cfg_line:
                continue
            rows = tr["timeTableRows"]
            dep = next((r for r in rows if r["stationShortCode"] == origin_code and r["type"] == "DEPARTURE"), None)
            arr = next((r for r in rows if r["stationShortCode"] == dest_code and r["type"] == "ARRIVAL"), None)
            if not dep or not arr or rows.index(dep) >= rows.index(arr):
                continue
            
            from trains import parse_time, extract_best_time
            sched_time = parse_time(dep["scheduledTime"])
            text, best = extract_best_time(dep)
            platform = dep.get("commercialTrack", "—")
            results.append((sched_time, tr["trainNumber"], text, best, platform, rows))
        return results
    
    morning_trains = process_trains_for_route(morning_trains_raw, ORIGIN, DEST)
    evening_trains = process_trains_for_route(evening_trains_raw, DEST, ORIGIN)
    
    # Filter by time (07:00 and 15:00)
    morning_filtered = filter_by_time(morning_trains, 7, 0)
    evening_filtered = filter_by_time(evening_trains, 15, 0)
    
    html.write("<div class='train-columns'>")
    
    # Left: Morning commute (07:00)
    html.write("<div>")
    html.write(f"<h4 style='margin-top:0;'>{origin_name} → {dest_name}</h4>")
    if not morning_filtered:
        html.write("<p><i>No trains found.</i></p>")
    else:
        for sched_time, num, text, best_dt, plat, rows in morning_filtered:
            html.write("<div style='margin-bottom:4px;'>")
            html.write(f"To {dest_name} ({TRAIN_LINE} {num}) — {text}")
            html.write(f"<br><span style='font-size:13px; opacity:0.8;'>Platform {plat}</span>")
            html.write("</div>")
    html.write("</div>")
    
    # Right: Evening commute (15:00)
    html.write("<div>")
    html.write(f"<h4 style='margin-top:0;'>{dest_name} → {origin_name}</h4>")
    if not evening_filtered:
        html.write("<p><i>No trains found.</i></p>")
    else:
        for sched_time, num, text, best_dt, plat, rows in evening_filtered:
            html.write("<div style='margin-bottom:4px;'>")
            html.write(f"To {origin_name} ({TRAIN_LINE} {num}) — {text}")
            html.write(f"<br><span style='font-size:13px; opacity:0.8;'>Platform {plat}</span>")
            html.write("</div>")
    html.write("</div>")
    
    html.write("</div>")  # end typical commute section

    # --- Auto-resize script (lets Streamlit iframe fit content height) ---
    html.write("""
    <script>
        window.addEventListener('load', function() {
            const height = document.body.scrollHeight;
            window.parent.postMessage(
                {isStreamlitMessage: true, type: "streamlit:setFrameHeight", height: height},
                "*"
            );
        });
    </script>
    """)

    html.write("</body></html>")
    return html.getvalue()

# ----------------------------
# 4) STANDALONE PREVIEW
# ----------------------------
if __name__ == "__main__":
    with open("trains_preview.html", "w", encoding="utf-8") as f:
        f.write(render_trains_html())
    print("✅ Saved: trains_preview.html")

    import webbrowser
    import os

    file_path = os.path.abspath("trains_preview.html")
    webbrowser.open(f"file://{file_path}")