import requests
import argparse
import csv
from datetime import datetime, timedelta, timezone

def main():
    parser = argparse.ArgumentParser(description="Finnish 15-min Spot Price Dashboard")
    # Setting default to 0 so 'no argument' = 'today'
    parser.add_argument('--past', type=int, default=0, help="Days into the past (default 0 = today)")
    parser.add_argument('--csv', action='store_true', help="Export to spot_prices.csv")
    args = parser.parse_args()

    # 1. Logic for "Today 00:00" Finnish Time
    # Get current local time and strip to midnight
    now_local = datetime.now().astimezone()
    start_local = (now_local - timedelta(days=args.past)).replace(hour=0, minute=0, second=0, microsecond=0)
    
    # Convert local midnight to UTC for the API
    start_utc = start_local.astimezone(timezone.utc)
    start_iso = start_utc.strftime('%Y-%m-%dT%H:%M:%S.000Z')

    # 2. Fetch Data
    url = f"https://sahkotin.fi/prices?quarter&fix&vat&start={start_iso}"
    
    print(f"Requesting data starting from: {start_local.strftime('%d.%m.%Y %H:%M')} (Local)")
    
    try:
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        data = r.json().get('prices', [])
    except Exception as e:
        print(f"❌ Error: {e}")
        return

    # 3. Filter and Format
    csv_rows = []
    print(f"\n{'Time (Finnish)':<18} | {'Price (c / kWh)'}")
    print("-" * 40)

    for entry in data:
        # Convert API UTC time back to Local Finnish time
        utc_dt = datetime.fromisoformat(entry['date'].replace('Z', '+00:00'))
        local_dt = utc_dt.astimezone()
        
        # Filter: Only show data from our intended start_local onwards
        if local_dt >= start_local:
            price = round(entry['value'], 3)
            time_display = local_dt.strftime('%d.%m. %H:%M')
            
            print(f"{time_display:<18} | {price:>11.3f} c")
            
            csv_rows.append([
                local_dt.strftime('%Y-%m-%d %H:%M'), 
                str(price).replace('.', ','), # Finnish Excel format
            ])

    # 4. CSV Export
    if args.csv and csv_rows:
        filename = 'spot_prices.csv'
        with open(filename, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f, delimiter=';')
            writer.writerow(['Timestamp', 'Price_c_kWh'])
            writer.writerows(csv_rows)
        print(f"\n✅ Exported {len(csv_rows)} rows to {filename}")

if __name__ == "__main__":
    main()