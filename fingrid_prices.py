"""
Electricity spot price client using sähkötin.fi API.
Provides 15-minute interval prices including VAT and service fees.
"""

import requests
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Tuple
from zoneinfo import ZoneInfo

# Constants
TZ = ZoneInfo("Europe/Helsinki")
SAHKOTIN_URL = "https://sahkotin.fi/prices?quarter&fix&vat"

def fetch_prices(start_time: datetime) -> List[Dict]:
    """
    Fetch prices from sähkötin.fi starting from start_time.
    
    Args:
        start_time: Datetime object (UTC or with timezone)
    """
    # Convert to UTC ISO format for the API
    start_utc = start_time.astimezone(timezone.utc)
    start_iso = start_utc.strftime('%Y-%m-%dT%H:%M:%S.000Z')
    
    url = f"{SAHKOTIN_URL}&start={start_iso}"
    
    try:
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        return r.json().get('prices', [])
    except Exception as e:
        print(f"Error fetching prices: {e}")
        return []

def get_plus_minus_24h_prices() -> List[Dict]:
    """
    Get prices starting from 24 hours ago up to the latest available (tomorrow included if available).
    """
    now = datetime.now(TZ)
    # Start from 24 hours ago
    start_time = now - timedelta(hours=24)
    
    # The API returns everything from start_time onwards
    data = fetch_prices(start_time)
    
    # We could filter to end at now + 24h if there's too much data,
    # but usually tomorrow's prices are only available for the next ~24-36h anyway.
    end_time = now + timedelta(hours=24)
    
    filtered_data = []
    for entry in data:
        # Convert API UTC time back to Local Finnish time
        utc_dt = datetime.fromisoformat(entry['date'].replace('Z', '+00:00'))
        local_dt = utc_dt.astimezone(TZ)
        
        if start_time <= local_dt <= end_time:
            filtered_data.append({
                'startTime': entry['date'], # Keep original for compatibility if needed
                'value': entry['value'],
                'localTime': local_dt,
                'localEndTime': local_dt + timedelta(minutes=15)
            })
            
    return filtered_data

def prepare_chart_data(price_data: List[Dict]) -> Tuple[List[datetime], List[float]]:
    """
    Transform price data into chart-ready format.
    
    Returns:
        Tuple of (timestamps, prices_in_snt_kWh)
    """
    timestamps = []
    prices = []

    for item in price_data:
        timestamps.append(item['localTime'])
        prices.append(item['value'])

    return timestamps, prices

def get_price_summary(price_data: List[Dict]) -> Dict[str, float]:
    """
    Calculate summary statistics (min, max, avg).
    """
    if not price_data:
        return {"min": 0.0, "max": 0.0, "avg": 0.0}

    values = [item['value'] for item in price_data]
    
    return {
        "min": min(values),
        "max": max(values),
        "avg": sum(values) / len(values),
    }

if __name__ == "__main__":
    # Test
    print("Testing Sähkötin price fetch (±24h)...")
    prices = get_plus_minus_24h_prices()
    if prices:
        print(f"Fetched {len(prices)} price points.")
        summary = get_price_summary(prices)
        print(f"Avg: {summary['avg']:.2f} snt/kWh")
        print(f"Min: {summary['min']:.2f} snt/kWh")
        print(f"Max: {summary['max']:.2f} snt/kWh")
    else:
        print("No data fetched.")
