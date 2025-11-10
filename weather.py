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
from typing import Dict, List, Optional, Set, Tuple
from zoneinfo import ZoneInfo

import requests
import xml.etree.ElementTree as ET

try:
    from astral import LocationInfo  # type: ignore
except ImportError:  # pragma: no cover - Astral optional
    LocationInfo = None

try:  # Astral 2.x exposes AstralError via astral; 3.x removed it
    from astral import AstralError  # type: ignore
except ImportError:  # pragma: no cover - fallback for versions without AstralError
    AstralError = Exception  # type: ignore

from astral.sun import sun

# -----------------------------------
# DEFAULT CONFIGURATION
# -----------------------------------
DEFAULT_PLACE = "Helsinki"
DEFAULT_FORECAST_HOURS = 24
try:
    DEFAULT_TIMEZONE = ZoneInfo("Europe/Helsinki")
except Exception:  # pragma: no cover - fallback for systems without timezone database
    DEFAULT_TIMEZONE = datetime.timezone.utc
STORED_QUERY = "fmi::forecast::harmonie::surface::point::multipointcoverage"
STEP_MIN = 60

_PARAMETER_MAP = {
    "precipitation_amount": "PrecipitationAmount",
    "precipitation": "PrecipitationAmount",
    "temperature": "Temperature",
    "windspeedms": "WindSpeedMS",
    "wind_speed": "WindSpeedMS",
    "weather_symbol3": "WeatherSymbol3",
}

ICON_BASE_URL = "https://cdn.fmi.fi/symbol-images/smartsymbol/v3/p"

# Descriptions copied from FMI SmartSymbol documentation so wording matches the
# icon set shown on https://en.ilmatieteenlaitos.fi/weather-symbols.
SMART_SYMBOL_DESCRIPTIONS: Dict[int, str] = {
    1: "clear",
    2: "mostly clear",
    4: "partly cloudy",
    6: "mostly cloudy",
    7: "overcast",
    9: "fog",
    11: "drizzle",
    14: "freezing drizzle",
    17: "freezing rain",
    21: "isolated showers",
    24: "scattered showers",
    27: "showers",
    31: "partly cloudy and periods of light rain",
    32: "partly cloudy and periods of moderate rain",
    33: "partly cloudy and periods of heavy rain",
    34: "mostly cloudy and periods of light rain",
    35: "mostly cloudy and periods of moderate rain",
    36: "mostly cloudy and periods of heavy rain",
    37: "light rain",
    38: "moderate rain",
    39: "heavy rain",
    41: "isolated light sleet showers",
    42: "isolated moderate sleet showers",
    43: "isolated heavy sleet showers",
    44: "scattered light sleet showers",
    45: "scattered moderate sleet showers",
    46: "scattered heavy sleet showers",
    47: "light sleet",
    48: "moderate sleet",
    49: "heavy sleet",
    51: "isolated light snow showers",
    52: "isolated moderate snow showers",
    53: "isolated heavy snow showers",
    54: "scattered light snow showers",
    55: "scattered moderate snow showers",
    56: "scattered heavy snow showers",
    57: "light snowfall",
    58: "moderate snowfall",
    59: "heavy snowfall",
    61: "isolated hail showers",
    64: "scattered hail showers",
    67: "hail showers",
    71: "isolated thundershowers",
    74: "scattered thundershowers",
    77: "thundershowers",
}

# Map legacy FMI WeatherSymbol3 codes to the closest SmartSymbol equivalents so
# we can keep supporting old feeds while rendering modern iconography.
LEGACY_SYMBOL_REDIRECTS: Dict[int, int] = {
    0: 1,
    3: 6,
    5: 6,
    8: 9,
    10: 11,
    12: 14,
    13: 14,
    15: 17,
    16: 17,
    18: 21,
    19: 24,
    20: 27,
    21: 37,
    22: 38,
    23: 39,
    24: 31,
    25: 32,
    26: 33,
    28: 34,
    29: 35,
    30: 36,
    31: 57,
    32: 58,
    33: 59,
    41: 24,
    42: 27,
    43: 27,
    51: 77,
    61: 47,
    62: 48,
    63: 49,
    71: 71,
    72: 74,
    73: 77,
    81: 71,
    82: 74,
    83: 77,
    91: 71,
    92: 74,
    93: 77,
}


def _normalize_symbol_code(code: int) -> Optional[int]:
    """Translate legacy symbol codes to SmartSymbol codes when possible."""
    visited: Set[int] = set()
    candidate = code
    while True:
        if candidate in SMART_SYMBOL_DESCRIPTIONS:
            return candidate
        if candidate in LEGACY_SYMBOL_REDIRECTS:
            next_candidate = LEGACY_SYMBOL_REDIRECTS[candidate]
            if next_candidate in visited:
                break
            visited.add(candidate)
            candidate = next_candidate
            continue
        break
    return None

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
        _config["forecast_hours"] = max(1, forecast_hours)


# -----------------------------------
# CORE FORECAST FETCH
# -----------------------------------
def _fetch_forecast(parameter: str, *, place: Optional[str] = None,
                    forecast_hours: Optional[int] = None):
    """Fetch forecast values and geolocation from FMI Open Data for a given parameter."""
    now = datetime.datetime.now(datetime.UTC)
    place = place or _config["place"]
    forecast_hours = forecast_hours or _config["forecast_hours"]
    starttime = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    endtime = (now + datetime.timedelta(hours=forecast_hours)).strftime("%Y-%m-%dT%H:%M:%SZ")

    fmi_parameter = _PARAMETER_MAP.get(parameter.lower(), parameter)
    url = (
        "https://opendata.fmi.fi/wfs?"
        f"service=WFS&version=2.0.0&request=getFeature"
        f"&storedquery_id={STORED_QUERY}"
        f"&place={place}"
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
    values: List[Optional[float]] = []
    for block in root.findall(".//omso:GridSeriesObservation//gml:doubleOrNilReasonTupleList", _NS):
        text = block.text.strip() if block.text else ""
        for v in text.split():
            try:
                value = float(v)
                if math.isnan(value):
                    values.append(None)
                else:
                    values.append(value)
            except ValueError:
                continue

    if not values:
        return [], location, None

    times = [now + datetime.timedelta(hours=i) for i in range(len(values))]
    return list(zip(times, values)), location, None


# -----------------------------------
# TIME & SUN HELPERS
# -----------------------------------
def _coerce_timezone(tz: Optional[ZoneInfo]) -> datetime.tzinfo:
    if tz is not None:
        return tz
    return DEFAULT_TIMEZONE


def _safe_astimezone(dt: datetime.datetime, tz: datetime.tzinfo) -> datetime.datetime:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.timezone.utc)
    return dt.astimezone(tz)


def _format_day_length(delta: Optional[datetime.timedelta]) -> Optional[str]:
    if not delta:
        return None
    seconds = int(delta.total_seconds())
    hours, remainder = divmod(seconds, 3600)
    minutes = remainder // 60
    return f"{hours} h {minutes:02d} min"


def daylight_info(lat: float, lon: float, *, date: Optional[datetime.date] = None,
                  tz: Optional[ZoneInfo] = None) -> Tuple[Optional[datetime.datetime],
                                                         Optional[datetime.datetime],
                                                         Optional[datetime.timedelta]]:
    """Return (sunrise, sunset, day_length) for the given coordinate."""
    tzinfo = _coerce_timezone(tz)
    target_date = date or _safe_astimezone(datetime.datetime.now(datetime.UTC), tzinfo).date()

    if LocationInfo is None:
        return None, None, None

    timezone_name = tzinfo.key if hasattr(tzinfo, "key") else "Europe/Helsinki"
    location = LocationInfo(latitude=lat, longitude=lon, timezone=timezone_name)
    try:
        sun_events = sun(location.observer, date=target_date, tzinfo=tzinfo)
    except AstralError:
        return None, None, None

    sunrise = sun_events.get("sunrise")
    sunset = sun_events.get("sunset")
    day_length = None
    if sunrise and sunset:
        day_length = sunset - sunrise
    return sunrise, sunset, day_length


def daylight_summary(lat: float, lon: float, *, date: Optional[datetime.date] = None,
                     tz: Optional[ZoneInfo] = None) -> Dict[str, Optional[str]]:
    tzinfo = _coerce_timezone(tz)
    sunrise, sunset, length = daylight_info(lat, lon, date=date, tz=tzinfo)
    return {
        "sunrise": sunrise.strftime("%H:%M") if sunrise else None,
        "sunset": sunset.strftime("%H:%M") if sunset else None,
        "day_length": _format_day_length(length),
        "sunrise_dt": sunrise,
        "sunset_dt": sunset,
    }


def _weather_symbol_description(symbol: Optional[float]) -> str:
    if symbol is None:
        return "Unknown"
    code = int(round(symbol))
    normalized = _normalize_symbol_code(code)
    if normalized is not None:
        return SMART_SYMBOL_DESCRIPTIONS[normalized]
    return f"Weather symbol {code}"


def _weather_symbol_icon(symbol: Optional[float], daylight: bool) -> Optional[str]:
    if symbol is None:
        return None
    code = int(round(symbol))
    normalized = _normalize_symbol_code(code)
    if normalized is None:
        return None
    icon_code = normalized if daylight else normalized + 100
    return f"{ICON_BASE_URL}/{icon_code}.svg"


def _value_at(
    forecasts: List[Tuple[datetime.datetime, Optional[float]]],
    target: datetime.datetime,
) -> Optional[float]:
    if not forecasts:
        return None
    idx = _find_closest_index(forecasts, target)
    if idx is None:
        return None
    value = forecasts[idx][1]
    if value is not None:
        return value

    # Fall back to nearest non-empty neighbour so minor gaps don't wipe data
    max_radius = min(len(forecasts), 6)
    for offset in range(1, max_radius):
        lower = idx - offset
        upper = idx + offset
        if lower >= 0:
            candidate = forecasts[lower][1]
            if candidate is not None:
                return candidate
        if upper < len(forecasts):
            candidate = forecasts[upper][1]
            if candidate is not None:
                return candidate
    return None


def interval_forecast(place: str, *, start_hour: int = 8, total_hours: int = 24,
                      step_hours: int = 4, tz: Optional[ZoneInfo] = None,
                      forecast_hours: int = 48) -> Tuple[Optional[Dict], Optional[str]]:
    """Build structured forecast for a place over fixed intervals."""
    if total_hours % step_hours != 0:
        return None, "❌ total_hours must be divisible by step_hours"

    tzinfo = _coerce_timezone(tz)
    now_local = _safe_astimezone(datetime.datetime.now(datetime.UTC), tzinfo)
    start_local = datetime.datetime.combine(
        now_local.date(), datetime.time(hour=start_hour), tzinfo
    )
    if start_local <= now_local:
        start_local += datetime.timedelta(days=1)

    try:
        padding = max(forecast_hours, total_hours + 4)
        precip, location, err = _fetch_forecast(
            "precipitation_amount", place=place, forecast_hours=padding
        )
        if err:
            return None, err
        temps, loc2, err = _fetch_forecast(
            "temperature", place=place, forecast_hours=padding
        )
        if err:
            return None, err
        winds, loc3, err = _fetch_forecast(
            "windspeedms", place=place, forecast_hours=padding
        )
        if err:
            return None, err
        symbols, loc4, err = _fetch_forecast(
            "weather_symbol3", place=place, forecast_hours=padding
        )
        if err:
            return None, err
    except Exception as e:
        return None, f"❌ Failed to fetch forecast: {e}"

    location = loc4 or loc3 or loc2 or location
    lat_lon = location if location else (None, None)

    steps = total_hours // step_hours
    intervals = []
    daylight_cache: Dict[datetime.date, Dict[str, Optional[str]]] = {}

    for i in range(steps):
        interval_start = start_local + datetime.timedelta(hours=step_hours * i)
        interval_end = interval_start + datetime.timedelta(hours=step_hours)

        symbol_val = _value_at(symbols, interval_start)
        raw_symbol_code = int(round(symbol_val)) if symbol_val is not None else None
        normalized_symbol_code = (
            _normalize_symbol_code(raw_symbol_code) if raw_symbol_code is not None else None
        )
        temp_val = _value_at(temps, interval_start)
        wind_val = _value_at(winds, interval_start)
        rain_val = _value_at(precip, interval_start)

        daylight_key = interval_start.date()
        if daylight_key not in daylight_cache and all(lat_lon):
            daylight_cache[daylight_key] = daylight_summary(
                lat_lon[0], lat_lon[1], date=daylight_key, tz=tzinfo
            )
        daylight_info_for_day = daylight_cache.get(daylight_key, {})
        sunrise_dt = daylight_info_for_day.get("sunrise_dt")
        sunset_dt = daylight_info_for_day.get("sunset_dt")
        is_daylight = False
        if sunrise_dt and sunset_dt:
            is_daylight = sunrise_dt <= interval_start < sunset_dt

        intervals.append(
            {
                "label": f"{interval_start.strftime('%H:%M')}–{interval_end.strftime('%H:%M')}",
                "start": interval_start,
                "end": interval_end,
                "temperature_c": temp_val,
                "wind_ms": wind_val,
                "precip_mm": max(rain_val, 0.0) if rain_val is not None else None,
                "raw_symbol_code": raw_symbol_code,
                "symbol_code": (
                    normalized_symbol_code
                    if normalized_symbol_code is not None
                    else raw_symbol_code
                ),
                "symbol_description": _weather_symbol_description(symbol_val),
                "icon_url": _weather_symbol_icon(symbol_val, is_daylight),
                "is_daylight": is_daylight,
            }
        )

    return {
        "place": place,
        "start": start_local,
        "end": intervals[-1]["end"] if intervals else None,
        "intervals": intervals,
        "location": lat_lon,
    }, None


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
    forecasts, _, error = _fetch_forecast("precipitation_amount")
    if error:
        return error
    if not forecasts:
        return "📭 No rain data."

    rain_intensity = []
    for timestamp, amount in forecasts:
        if amount is None:
            continue
        rate = max(amount, 0.0)
        rain_intensity.append((timestamp, rate))

    if not rain_intensity:
        return "📭 No rain data."

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

    values: List[float] = []
    current: Optional[float] = None
    for _, reading in forecasts:
        if reading is None:
            continue
        if current is None:
            current = reading
        values.append(reading)

    if current is None or not values:
        return "📭 No temperature data."

    return (
        f"🌡️ Now: {current:.1f}°C | Range: {min(values):.1f}°C – {max(values):.1f}°C"
    )


def wind():
    forecasts, _, error = _fetch_forecast("windspeedms")
    if error:
        return error
    if not forecasts:
        return "📭 No wind data."

    values: List[float] = []
    current: Optional[float] = None
    for _, reading in forecasts:
        if reading is None:
            continue
        if current is None:
            current = reading
        values.append(reading)

    if current is None or not values:
        return "📭 No wind data."

    return f"💨 Now: {current:.1f} m/s | Max: {max(values):.1f} m/s"


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

    rain_rate = _value_at(rain_data, target_time)
    temp_val = _value_at(temp_data, target_time)
    wind_val = _value_at(wind_data, target_time)

    if any(v is None for v in (rain_rate, temp_val, wind_val)):
        return None, "📭 No forecast available for that time."

    metrics = {
        "target_time": target_time,
        "rain_mm": max(rain_rate, 0.0) if rain_rate is not None else None,
        "temperature_c": temp_val,
        "wind_ms": wind_val,
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

    effective_hours = max(1, args.hours)
    set_config(place=args.place, forecast_hours=effective_hours)

    if args.time:
        print(weather_at(args.time))
    else:
        print(f"📍 Forecast for {args.place} (next {effective_hours}h):")
        rain_summary = rain()
        temp_summary = temperature()
        wind_summary = wind()
        print(f"{rain_summary} | {temp_summary} | {wind_summary}")

# -----------------------------------
# UMBRELLA CHECK (adaptive threshold)
# -----------------------------------
def umbrella_needed_tomorrow() -> tuple[bool, str]:
    """
    Check forecast for tomorrow's commute (Kyrölä↔Helsinki).

    Morning: Kyrölä 07–08, Helsinki 08–09
    Afternoon: Helsinki 15–17, Kyrölä 16–18

    Returns:
        (need_umbrella: bool, icon: str)
    """
    checks = [
        ("Kyrölä", "tomorrow 07:30"),
        ("Helsinki", "tomorrow 08:30"),
        ("Helsinki", "tomorrow 16:00"),
        ("Kyrölä", "tomorrow 17:00"),
    ]

    max_rain = 0.0
    for place, time_str in checks:
        set_config(place=place, forecast_hours=36)
        metrics, error = weather_metrics(time_str)
        if error or metrics is None:
            continue
        rain = metrics["rain_mm"] or 0.0
        max_rain = max(max_rain, rain)

    # Adaptive classification
    if max_rain >= 5.0:
        return True, "☔"   # heavy rain
    elif max_rain >= 2.0:
        return True, "☂️"   # moderate rain
    elif max_rain >= 0.5:
        return True, "🌂"   # light rain
    else:
        return False, "🌤️"  # dry


if __name__ == "__main__":
    main()
