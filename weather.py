"""
weather.py
----------
Fetches weather forecast from FMI open data (HARMONIE model).
Provides rain, temperature, and wind forecasts, and point forecasts for specific times.

Usage examples:
    py weather.py -place Paippinen -time 08:00      (forecast for Paippinen at 8:00)
    py weather.py                                   (default; Helsinki, next 24h)
    py weather.py -place Kyrölä -hours 48           (forecast for Kyrölä next 48h)
    py weather.py -place "Södra Paipis" -time "tomorrow 14:30" (forecast for Södra Paipis tomorrow at 14:30)
"""

import argparse
import datetime
import math
import requests
import xml.etree.ElementTree as ET

# -----------------------------------
# DEFAULT CONFIGURATION
# -----------------------------------
DEFAULT_PLACE = "Helsinki"
DEFAULT_FORECAST_HOURS = 24
STORED_QUERY = "fmi::forecast::harmonie::surface::point::multipointcoverage"
STEP_MIN = 60

_PARAMETER_MAP = {
    "precipitation_amount": "PrecipitationAmount",
    "precipitation": "PrecipitationAmount",
    "temperature": "Temperature",
    "windspeedms": "WindSpeedMS",
    "wind_speed": "WindSpeedMS",
}

_NS = {
    "wfs": "http://www.opengis.net/wfs/2.0",
    "om": "http://www.opengis.net/om/2.0",
    "gml": "http://www.opengis.net/gml/3.2",
    "omso": "http://inspire.ec.europa.eu/schemas/omso/3.0",
    "gmlcov": "http://www.opengis.net/gmlcov/1.0",
}

_config = {
    "place": DEFAULT_PLACE,
    "forecast_hours": DEFAULT_FORECAST_HOURS
}


# -----------------------------------
# CONFIG HELPERS
# -----------------------------------
def set_config(place=None, forecast_hours=None):
    if place is not None:
        _config["place"] = place
    if forecast_hours is not None:
        _config["forecast_hours"] = forecast_hours


# -----------------------------------
# CORE FORECAST FETCH
# -----------------------------------
def _fetch_forecast(parameter):
    """Fetch forecast values and geolocation from FMI Open Data for a given parameter."""
    now = datetime.datetime.now(datetime.UTC)
    starttime = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    endtime = (now + datetime.timedelta(hours=_config["forecast_hours"])).strftime("%Y-%m-%dT%H:%M:%SZ")

    fmi_parameter = _PARAMETER_MAP.get(parameter.lower(), parameter)
    url = (
        "https://opendata.fmi.fi/wfs?"
        f"service=WFS&version=2.0.0&request=getFeature"
        f"&storedquery_id={STORED_QUERY}"
        f"&place={_config['place']}"
        f"&parameters={fmi_parameter}"
        f"&starttime={starttime}"
        f"&endtime={endtime}"
        f"&timestep={STEP_MIN}"
    )

    try:
        r = requests.get(url, timeout=20)
        r.raise_for_status()
    except Exception as e:
        return [], None, f"❌ Failed to fetch FMI forecast: {e}"

    root = ET.fromstring(r.content)
    ns = _NS.copy()
    ns["sams"] = "http://www.opengis.net/samplingSpatial/2.0"

    # Extract location
    pos_elem = root.find(".//sams:shape//gml:pos", ns)
    location = None
    if pos_elem is not None and pos_elem.text:
        coords = pos_elem.text.strip().split()
        if len(coords) == 2:
            lat, lon = map(float, coords)
            location = (lat, lon)

    # Extract values
    values = []
    for block in root.findall(".//omso:GridSeriesObservation//gml:doubleOrNilReasonTupleList", _NS):
        text = block.text.strip() if block.text else ""
        for v in text.split():
            try:
                value = float(v)
                if math.isnan(value):
                    value = 0.0
                values.append(value)
            except ValueError:
                continue

    if not values:
        return [], location, None

    times = [now + datetime.timedelta(hours=i) for i in range(len(values))]
    return list(zip(times, values)), location, None


# -----------------------------------
# UTILITY HELPERS
# -----------------------------------
def _parse_time_string(time_str):
    now = datetime.datetime.now()
    t = time_str.lower().strip()

    if t.startswith("tomorrow"):
        time_part = t.replace("tomorrow", "").strip()
        target_time = datetime.datetime.strptime(time_part, "%H:%M").time()
        target = datetime.datetime.combine(now.date() + datetime.timedelta(days=1), target_time)
    else:
        target_time = datetime.datetime.strptime(t, "%H:%M").time()
        target = datetime.datetime.combine(now.date(), target_time)
        if target < now:
            target += datetime.timedelta(days=1)
    return target


def _find_closest_index(forecasts, target_time):
    if not forecasts:
        return None
    target_utc = target_time.astimezone(datetime.UTC)
    return min(range(len(forecasts)), key=lambda i: abs(forecasts[i][0] - target_utc))


# -----------------------------------
# INDIVIDUAL FORECASTS
# -----------------------------------
def rain():
    forecasts, location, error = _fetch_forecast("precipitation_amount")
    if error:
        return error
    if not forecasts:
        return "📭 No rain data."

    rain_intensity = []
    for timestamp, amount in forecasts:
        rate = max(amount, 0.0)
        rain_intensity.append((timestamp, rate))

    rain_events = [(t, rate) for t, rate in rain_intensity if rate > 0.1]
    if rain_events:
        first_rain = rain_events[0]
        t_local = first_rain[0].astimezone().strftime("%a %H:%M")
        rate = first_rain[1]
        if rate >= 5.0:
            icon = "⛈️"
        elif rate >= 1.0:
            icon = "🌧️"
        else:
            icon = "🌦️"
        return f"{icon} Rain expected {t_local} ({rate:.1f} mm/h)."
    else:
        return "☀️ No rain forecast."


def temperature():
    forecasts, _, error = _fetch_forecast("temperature")
    if error:
        return error
    if not forecasts:
        return "📭 No temperature data."

    current = forecasts[0][1]
    vals = [v for _, v in forecasts]
    return f"🌡️ Now: {current:.1f}°C | Range: {min(vals):.1f}°C – {max(vals):.1f}°C"


def wind():
    forecasts, _, error = _fetch_forecast("windspeedms")
    if error:
        return error
    if not forecasts:
        return "📭 No wind data."

    current = forecasts[0][1]
    vals = [v for _, v in forecasts]
    return f"💨 Now: {current:.1f} m/s | Max: {max(vals):.1f} m/s"


# -----------------------------------
# WEATHER AT SPECIFIC TIME
# -----------------------------------
def _collect_weather_metrics(time_str: str):
    """Return forecast metrics (rain, temperature, wind) near the given time."""
    try:
        target_time = _parse_time_string(time_str)
    except ValueError:
        return None, f"❌ Invalid time format '{time_str}'"

    now = datetime.datetime.now()
    max_time = now + datetime.timedelta(hours=_config["forecast_hours"])
    if target_time > max_time:
        return None, f"⚠️ Requested time beyond forecast range ({_config['forecast_hours']}h)"

    rain_data, _, err_rain = _fetch_forecast("precipitation_amount")
    temp_data, _, err_temp = _fetch_forecast("temperature")
    wind_data, _, err_wind = _fetch_forecast("windspeedms")

    if err_rain or err_temp or err_wind:
        return None, "❌ Failed to fetch forecast data"

    rain_idx = _find_closest_index(rain_data, target_time)
    temp_idx = _find_closest_index(temp_data, target_time)
    wind_idx = _find_closest_index(wind_data, target_time)

    if any(idx is None for idx in (rain_idx, temp_idx, wind_idx)):
        return None, "📭 No forecast available for that time."

    rain_rate = max(rain_data[rain_idx][1], 0.0)

    metrics = {
        "target_time": target_time,
        "rain_mm": rain_rate,
        "temperature_c": temp_data[temp_idx][1],
        "wind_ms": wind_data[wind_idx][1],
    }
    return metrics, None


def weather_metrics(time_str: str):
    """Expose raw weather metrics for external callers."""
    return _collect_weather_metrics(time_str)


def weather_at(time_str: str):
    """Return compact weather summary for configured location near given time."""
    metrics, error = _collect_weather_metrics(time_str)
    if error:
        return error

    rain_mm = metrics["rain_mm"]
    temp_c = metrics["temperature_c"]
    wind_ms = metrics["wind_ms"]

    # Rain icon
    if rain_mm < 0.1:
        rain_icon = "☀️"
    elif rain_mm < 1.0:
        rain_icon = "🌦️"
    elif rain_mm < 5.0:
        rain_icon = "🌧️"
    else:
        rain_icon = "⛈️"

    # Temperature icon
    if temp_c < 0:
        temp_icon = "❄️"
    else:
        temp_icon = "🌡️"

    # Wind icon
    if wind_ms < 1:
        wind_icon = "🍃"
    else:
        wind_icon = "💨"

    return (
        f"{rain_icon} {rain_mm:.1f} mm/h, {temp_icon} {temp_c:.1f} °C, {wind_icon} {wind_ms:.1f} m/s"
    )


# -----------------------------------
# CLI INTERFACE (simplified)
# -----------------------------------
def main():
    parser = argparse.ArgumentParser(description="FMI weather forecast CLI")
    parser.add_argument("-place", default=DEFAULT_PLACE, help="Location name (default: Helsinki)")
    parser.add_argument("-time", help="Specific time (HH:MM or 'tomorrow HH:MM')")
    parser.add_argument("-hours", type=int, default=DEFAULT_FORECAST_HOURS,
                        help="Forecast range in hours (default: 24)")
    args = parser.parse_args()

    set_config(place=args.place, forecast_hours=args.hours)

    if args.time:
        print(weather_at(args.time))
    else:
        print(f"📍 Forecast for {args.place} (next {args.hours}h):")
        rain_summary = rain()
        temp_summary = temperature()
        wind_summary = wind()
        print(f"{rain_summary} | {temp_summary} | {wind_summary}")


if __name__ == "__main__":
    main()
