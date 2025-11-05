Updated README.md (full text)
# 🚉 Commute Dashboard — Trains, Roads & Sensors

A live dashboard built with **Streamlit** and **Folium** that visualizes  
commuter data from Finland’s [Digitraffic](https://www.digitraffic.fi/en/) API.

It combines:
- 🚆 **Live train departures and arrivals**
- 🛣️ **Road conditions, weather, and sensors**
- 📷 **Traffic cameras and roadworks**
- 🌡️ **Weather station data, humidity, wind, and precipitation**
- 🚗 **Traffic measurement (speed & volume)**

---

## 🧭 Overview

This project brings together multiple data sources into one real-time web dashboard.

- **Top section:** Live train information between two configured stations (e.g. Ainola ↔ Helsinki)
- **Bottom section:** Interactive road map showing conditions, live sensor data, and roadworks
- **Data:** Pulled live from Digitraffic’s REST APIs for rail, road, and weather networks
- **Framework:** Streamlit + Folium (Leaflet) for visualization

Everything runs locally or on Streamlit Cloud without any server setup.

---

## 📦 Folder structure



r-commute-dashboard/
│
├── main.py # Streamlit entry point (dashboard layout)
├── trains_display.py # Fetches + renders live train departures/arrivals
├── roads_display.py # Creates Folium map with roads, sensors, weather
├── roads.py # Logic layer for road, weather, and sensor data
├── config.py # Configuration (API endpoints, coordinates, etc.)
├── config.json # Bounding box, markers, and API source definitions
└── README.md # This file


---

## ⚙️ Requirements

**Python version:** 3.10 or newer (tested on 3.13)

**Install dependencies:**
```bash
pip install -r requirements.txt


Typical packages used:

streamlit>=1.32
streamlit-autorefresh
requests
pandas
folium
branca
pytz

🚀 Running the dashboard

Run Streamlit from your project folder:

streamlit run main.py


Your browser will open at:

http://localhost:8501

Behavior

The train section loads first (fast).

The road & weather map loads asynchronously afterwards.

Map and data are cached for 5 minutes to reduce API load.

🌍 Data sources (Digitraffic APIs)
Data type	Endpoint	Example
Train schedules	https://rata.digitraffic.fi/api/v1/live-trains	/live-trains/station/AIN/HL
Road network	https://tie.digitraffic.fi/api/metadata/v3/maintenance-tracking	
Road condition forecasts	https://tie.digitraffic.fi/api/weather/v1/forecast-sections-simple	
Weather stations	https://tie.digitraffic.fi/api/weather/v1/stations	
Cameras	https://tie.digitraffic.fi/api/camera/v1/stations	
Traffic measurement (TMS)	https://tie.digitraffic.fi/api/tms/v1/stations	/stations/{id}/data

All data is public and updated by the Finnish Transport Infrastructure Agency (FTIA).

📡 APIs and Input Data

All live data is pulled from Digitraffic.fi
 public APIs.

Below is a summary of each API endpoint, the parameters used, and which JSON fields are consumed by the app.

1️⃣ Train Data (Digitraffic Railway API)

Endpoint:

https://rata.digitraffic.fi/api/v1/live-trains/station/{stationShortCode}


Used Parameters:

Parameter	Description	Example
stationShortCode	Short code for station	AIN, HKI
departing_trains	Filter to show only departures	true
arriving_trains	Filter to show only arrivals	false
include_nonstopping	Include trains passing without stop	false

Used Data Fields:

JSON Field	Meaning
trainType / commuterLineID	Used to identify R-trains
trainNumber	Train number (e.g., 9632)
timeTableRows	Each stop’s scheduled and actual times
scheduledTime, actualTime	Used to calculate delays
stationShortCode	Station identifier
commercialTrack	Platform number
cancelled	Boolean flag for disruptions
2️⃣ Road Forecasts (Weather Forecast Sections)

Endpoint:

https://tie.digitraffic.fi/api/weather/v1/forecast-sections-simple


Query Parameters (Bounding Box):

Parameter	Description	Example
xMin	Minimum longitude	24.8
yMin	Minimum latitude	60.3
xMax	Maximum longitude	25.5
yMax	Maximum latitude	60.7

Used Data Fields:

JSON Field	Meaning
roadNumber	Finnish national road number
forecastName	Description of segment
roadCondition	Surface condition (text or code)
roadTemperature	Surface temperature (°C)
3️⃣ Traffic Warnings and Roadworks (Traffic Message API)

Endpoint:

https://tie.digitraffic.fi/api/traffic-message/v1/messages


Used Data Fields:

JSON Field	Meaning
situationType	Type (e.g., ROAD_WORK, TRAFFIC_ANNOUNCEMENT, WEIGHT_RESTRICTION)
title, description	Human-readable message
geometry.coordinates	Location for bounding box filtering
releaseTime	Date/time when roadwork started
announcements[].locationDetails.roadAddressLocation.primaryPoint.roadName	Road name
announcements[].locationDetails.roadAddressLocation.primaryPoint.municipality	Municipality name

Only messages inside the configured bounding box (from config.json) are shown.

4️⃣ Weather and Sensor Stations

Endpoints:

https://tie.digitraffic.fi/api/weather/v1/stations
https://tie.digitraffic.fi/api/weather/v1/stations/{id}/data
https://tie.digitraffic.fi/api/weathercam/v1/stations


Used and Relevant Fields:

JSON Field	Meaning
ILMA	Air temperature (°C)
TIE_1, TIE_2	Road surface temperatures (°C)
KESKITUULI, MAKSIMITUULI	Average and max wind speeds (m/s)
KELI_1, KELI_2	Road surface state (dry, icy, etc.)
KITKA1	Friction coefficient (µ)
NÄKYVYYS_M	Visibility in meters
SADE, SADESUMMA	Rain status and precipitation (mm)
5️⃣ Traffic Measurement (TMS)

Endpoint:

https://tie.digitraffic.fi/api/tms/v1/stations/{id}/data


Used Data Fields:

JSON Field	Meaning
OHITUKSET_60MIN_KIINTEA_SUUNTA2	Vehicle volume (vehicles/hour)
KESKINOPEUS_5MIN_LIUKUVA_SUUNTA2	Average speed (km/h)
timeWindowStart, timeWindowEnd	Aggregation window
measuredTime	Time of measurement
unit	Unit of measurement (km/h, kpl/h)
🗺️ Features
🚆 Trains section

Displays next departures both to and from your commute destinations.

Automatically updates based on current time.

Dynamically adjusts height to fit content (no white gaps in Streamlit).

Configurable via config.py (ORIGIN, DEST, etc.).

🛣️ Roads map

Folium map with toggle menu (top-left) for:

Road conditions

Weather stations

Cameras

Traffic Measurement (TMS)

Roadworks

Markers:

☁ Weather station

📷 Camera

🚗 Traffic measurement (speed, volume)

🚧 Roadworks

🏠 Home marker

🚉 Train station marker

Legend (bottom-left) shows color and icon meanings.

Works in both dark and light Streamlit themes.

🌡️ Sensor data

Weather: temperature, humidity, wind speed, precipitation.

TMS: current traffic speed (km/h) and volume (vehicles/h).

Cameras: live or snapshot image URLs.

Updates automatically when map reloads.

🧰 Configuration
config.json

Defines:

Bounding box for the map

Station IDs for trains

Marker coordinates (e.g. home, Ainola station)

Optional API overrides

config.py

Provides helper functions to load configuration and expose constants to scripts.

🧪 Development

To debug or test individual modules:

python roads.py


Outputs a summary such as:

📡 Checking live sensors...
🌡 Weather stations: 23 found
📷 Cameras: 15 found
🚗 TMS stations: 5 found
   → TMS 20026: speed 87 km/h, volume 44 veh/h

🩺 Common troubleshooting
Issue	Likely cause	Fix
Map legend missing at 90 % zoom	CSS position: fixed → changed to absolute in legend block	✅ Fixed
TMS speed/volume missing	Old /tms-data/v1 endpoint	✅ Updated to /tms/v1
White gap under train table	Default <body> margin in iframe	✅ Fixed with body {margin:0} and auto height script
Map loads slowly	Folium HTML heavy	Cached via @st.cache_data(ttl=300)
📜 License

MIT License © 2025 — Birgir Einarson

This project uses open public data from Digitraffic (FTIA).
Data © Finnish Transport Infrastructure Agency, used under the Digitraffic Terms of Use
.

🙌 Acknowledgments

Digitraffic API
 for open transport data.

Streamlit
 for a fast interactive dashboard.

Folium / Leaflet
 for map rendering.

Enjoy your real-time commute dashboard!
If you improve it — such as adding alerts, push notifications, or dark-mode-aware legends — contributions are welcome.