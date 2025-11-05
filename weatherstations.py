import requests
import xml.etree.ElementTree as ET

# Bounding box limits
X_MIN, Y_MIN, X_MAX, Y_MAX = 24.8, 60.3, 25.5, 60.7

# FMI WFS endpoint
url = "https://opendata.fmi.fi/wfs"
params = {
    "service": "WFS",
    "version": "2.0.0",
    "request": "GetFeature",
    "storedquery_id": "fmi::ef::stations",
    # FMI's bbox parameter is unreliable — we'll filter manually
    "bbox": f"{X_MIN},{Y_MIN},{X_MAX},{Y_MAX}",
}

# Request and parse
response = requests.get(url, params=params)
response.raise_for_status()
root = ET.fromstring(response.content)

# XML namespaces
ns = {
    "wfs": "http://www.opengis.net/wfs/2.0",
    "ef": "http://inspire.ec.europa.eu/schemas/ef/4.0",
    "base": "http://inspire.ec.europa.eu/schemas/base/3.3",
    "gml": "http://www.opengis.net/gml/3.2",
}

stations = []

# Loop through station features
for facility in root.findall(".//ef:EnvironmentalMonitoringFacility", ns):
    # Try multiple tags for the station name
    name_elem = (
        facility.find(".//ef:officialName", ns)
        or facility.find(".//ef:name", ns)
        or facility.find(".//gml:name", ns)
    )
    name = name_elem.text.strip() if name_elem is not None else "(no name)"

    # FMI station ID (FMISID)
    id_elem = facility.find(".//base:localId", ns)
    fmisid = id_elem.text.strip() if id_elem is not None else "(no id)"

    # Position (lat lon)
    pos_elem = facility.find(".//gml:pos", ns)
    if pos_elem is not None:
        lat, lon = map(float, pos_elem.text.strip().split())

        # ✅ Apply strict bounding box filtering
        if X_MIN <= lon <= X_MAX and Y_MIN <= lat <= Y_MAX:
            stations.append({"id": fmisid, "name": name, "lat": lat, "lon": lon})

# Output
if stations:
    print(f"Stations in bounding box ({X_MIN}, {Y_MIN}) → ({X_MAX}, {Y_MAX}):")
    for s in sorted(stations, key=lambda x: x["name"]):
        print(f"  • ID: {s['id']}, Name: {s['name']}, Lat: {s['lat']:.4f}, Lon: {s['lon']:.4f}")
else:
    print("No stations found within the bounding box.")
