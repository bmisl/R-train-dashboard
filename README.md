# 🚉 Commute Dashboard — Trains, Roads & Sensors

A live dashboard built with **Streamlit** and **Folium** that visualizes  
commuter data from Finland’s [Digitraffic](https://www.digitraffic.fi/en/) API.

It combines:
- 🚆 **Live train departures and arrivals**
- 🔊 **R-train audio announcement button** (Helsinki window)
- 🛣️ **Road conditions, weather, and sensors**
- 📷 **Traffic cameras and roadworks**
- 🌡️ **Weather station data, humidity, wind, and precipitation**
- 🚗 **Traffic measurement (speed & volume)**

---

## 🧭 Overview

This project brings together multiple data sources into one real-time web dashboard.

- **Top section:** Live train information between two configured stations (e.g. Ainola ↔ Helsinki)
- **Audio prompt:** During the afternoon announcement window, click the train button to hear the next Helsinki R-train track and time.
- **Bottom section:** Interactive road map showing conditions, live sensor data, and roadworks
- **Data:** Pulled live from Digitraffic’s REST APIs for rail, road, and weather networks
- **Framework:** Streamlit + Folium (Leaflet) for visualization

Everything runs locally or on Streamlit Cloud without any server setup.

---

## 📦 Folder structure

```
r-commute-dashboard/
│
├── main.py              # Streamlit entry point (dashboard layout)
├── trains_display.py    # Fetches + renders live train departures/arrivals
├── roads_display.py     # Creates Folium map with roads, sensors, weather
├── roads.py             # Logic layer for road, weather, and sensor data
├── sensors.py           # (Legacy) extra sensor utilities
├── config.py            # Configuration (API endpoints, coordinates, etc.)
├── config.json          # Bounding box, markers, and API source definitions
└── README.md            # This file
```

---

## ⚙️ Requirements

**Python version:** 3.10 or newer (tested on 3.13)

**Install dependencies:**
```bash
pip install -r requirements.txt
```

Typical packages used:
```text
streamlit>=1.32
streamlit-autorefresh
requests
pandas
folium
branca
pytz
```

---

## 🚀 Running the dashboard

Run Streamlit from your project folder:

```bash
streamlit run main.py
```

Your browser will open at:

```
http://localhost:8501
```

### Behavior
- The **train section** loads first (fast).
- The **road & weather map** loads asynchronously afterwards.
- Map and data are cached for 5 minutes to reduce API load.

---

## 🌍 Data sources (Digitraffic APIs)

All data is public and updated by the Finnish Transport Infrastructure Agency (FTIA).

---

## 📡 APIs and Input Data

All live data is pulled from [Digitraffic.fi](https://www.digitraffic.fi/en/services/) public APIs.

Below is a summary of each API endpoint, the parameters used, and which JSON fields are consumed by the app.

---

### 1️⃣ Train Data (Digitraffic Railway API)

**Endpoint:**
```
https://rata.digitraffic.fi/api/v1/live-trains/station/{stationShortCode}
```

<table>
<tr><th>Parameter</th><th>Description</th><th>Example</th></tr>
<tr><td><code>stationShortCode</code></td><td>Short code for station</td><td>AIN, HKI</td></tr>
<tr><td><code>departing_trains</code></td><td>Filter to show only departures</td><td>true</td></tr>
<tr><td><code>arriving_trains</code></td><td>Filter to show only arrivals</td><td>false</td></tr>
<tr><td><code>include_nonstopping</code></td><td>Include trains passing without stop</td><td>false</td></tr>
</table>

**Used Data Fields:**

<table>
<tr><th>JSON Field</th><th>Meaning</th></tr>
<tr><td><code>trainType</code> / <code>commuterLineID</code></td><td>Used to identify R-trains</td></tr>
<tr><td><code>trainNumber</code></td><td>Train number (e.g., 9632)</td></tr>
<tr><td><code>timeTableRows</code></td><td>Each stop’s scheduled and actual times</td></tr>
<tr><td><code>scheduledTime</code>, <code>actualTime</code></td><td>Used to calculate delays</td></tr>
<tr><td><code>stationShortCode</code></td><td>Station identifier</td></tr>
<tr><td><code>commercialTrack</code></td><td>Platform number</td></tr>
<tr><td><code>cancelled</code></td><td>Boolean flag for disruptions</td></tr>
</table>

---

### 2️⃣ Road Forecasts (Weather Forecast Sections)

**Endpoint:**
```
https://tie.digitraffic.fi/api/weather/v1/forecast-sections-simple
```

**Query Parameters (Bounding Box):**
<table>
<tr><th>Parameter</th><th>Description</th><th>Example</th></tr>
<tr><td><code>xMin</code></td><td>Minimum longitude</td><td>24.8</td></tr>
<tr><td><code>yMin</code></td><td>Minimum latitude</td><td>60.3</td></tr>
<tr><td><code>xMax</code></td><td>Maximum longitude</td><td>25.5</td></tr>
<tr><td><code>yMax</code></td><td>Maximum latitude</td><td>60.7</td></tr>
</table>

**Used Data Fields:**
<table>
<tr><th>JSON Field</th><th>Meaning</th></tr>
<tr><td><code>roadNumber</code></td><td>Finnish national road number</td></tr>
<tr><td><code>forecastName</code></td><td>Description of segment</td></tr>
<tr><td><code>roadCondition</code></td><td>Surface condition (text or code)</td></tr>
<tr><td><code>roadTemperature</code></td><td>Surface temperature (°C)</td></tr>
</table>

---

### 3️⃣ Traffic Warnings and Roadworks (Traffic Message API)

**Endpoint:**
```
https://tie.digitraffic.fi/api/traffic-message/v1/messages
```

**Used Data Fields:**
<table>
<tr><th>JSON Field</th><th>Meaning</th></tr>
<tr><td><code>situationType</code></td><td>Type (e.g., ROAD_WORK, TRAFFIC_ANNOUNCEMENT)</td></tr>
<tr><td><code>title</code>, <code>description</code></td><td>Human-readable message</td></tr>
<tr><td><code>geometry.coordinates</code></td><td>Location for bounding box filtering</td></tr>
<tr><td><code>releaseTime</code></td><td>Date/time when roadwork started</td></tr>
<tr><td><code>roadAddressLocation.primaryPoint.roadName</code></td><td>Road name</td></tr>
<tr><td><code>roadAddressLocation.primaryPoint.municipality</code></td><td>Municipality name</td></tr>
</table>

Only messages inside the configured bounding box (from <code>config.json</code>) are shown.

---

### 4️⃣ Weather and Sensor Stations

**Endpoints:**
```
https://tie.digitraffic.fi/api/weather/v1/stations
https://tie.digitraffic.fi/api/weather/v1/stations/{id}/data
https://tie.digitraffic.fi/api/weathercam/v1/stations
```

**Used and Relevant Fields:**
<table>
<tr><th>JSON Field</th><th>Meaning</th></tr>
<tr><td><code>ILMA</code></td><td>Air temperature (°C)</td></tr>
<tr><td><code>TIE_1</code>, <code>TIE_2</code></td><td>Road surface temperatures (°C)</td></tr>
<tr><td><code>KESKITUULI</code>, <code>MAKSIMITUULI</code></td><td>Average and max wind speeds (m/s)</td></tr>
<tr><td><code>KELI_1</code>, <code>KELI_2</code></td><td>Road surface state (dry, icy, etc.)</td></tr>
<tr><td><code>KITKA1</code></td><td>Friction coefficient (µ)</td></tr>
<tr><td><code>NÄKYVYYS_M</code></td><td>Visibility in meters</td></tr>
<tr><td><code>SADE</code>, <code>SADESUMMA</code></td><td>Rain status and precipitation (mm)</td></tr>
</table>

---

### 5️⃣ Traffic Measurement (TMS)

**Endpoint:**
```
https://tie.digitraffic.fi/api/tms/v1/stations/{id}/data
```

**Used Data Fields:**
<table>
<tr><th>JSON Field</th><th>Meaning</th></tr>
<tr><td><code>OHITUKSET_60MIN_KIINTEA_SUUNTA2</code></td><td>Vehicle volume (vehicles/hour)</td></tr>
<tr><td><code>KESKINOPEUS_5MIN_LIUKUVA_SUUNTA2</code></td><td>Average speed (km/h)</td></tr>
<tr><td><code>timeWindowStart</code>, <code>timeWindowEnd</code></td><td>Aggregation window</td></tr>
<tr><td><code>measuredTime</code></td><td>Time of measurement</td></tr>
<tr><td><code>unit</code></td><td>Unit of measurement (km/h, kpl/h)</td></tr>
</table>

---

## 📜 License

MIT License © 2025 — Birgir Einarson

This project uses open public data from Digitraffic (FTIA).  
Data © Finnish Transport Infrastructure Agency, used under the [Digitraffic Terms of Use](https://www.digitraffic.fi/en/services/general/).

---

## 🙌 Acknowledgments

- [Digitraffic API](https://www.digitraffic.fi/en/) for open transport data.
- [Streamlit](https://streamlit.io/) for a fast interactive dashboard.
- [Folium / Leaflet](https://python-visualization.github.io/folium/) for map rendering.

---

**Enjoy your real-time commute dashboard!**
