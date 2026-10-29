import csv
from pathlib import Path
from urllib.request import urlopen

import truststore

truststore.inject_into_ssl()

project_dir = Path(__file__).resolve().parent
reports_dir = project_dir / "reports"
reports_dir.mkdir(exist_ok=True)

url = (
    "https://www.ncei.noaa.gov/pub/data/ghcn/daily/"
    "ghcnd-stations.txt"
)

print("Reading NOAA station catalog...", flush=True)

with urlopen(url, timeout=120) as response:
    catalog = response.read().decode("utf-8")

stations = []

for line in catalog.splitlines():
    if len(line) < 71:
        continue

    state = line[38:40].strip()

    if state != "DC":
        continue

    stations.append({
        "station_id": line[0:11].strip(),
        "name": line[41:71].strip(),
        "latitude": float(line[12:20]),
        "longitude": float(line[21:30]),
        "elevation_m": float(line[31:37]),
        "state": state,
    })

if not stations:
    raise ValueError("No stations marked DC were found.")

output_file = reports_dir / "dc_station_candidates.csv"

with output_file.open("w", newline="", encoding="utf-8") as file:
    writer = csv.DictWriter(
        file,
        fieldnames=list(stations[0]),
    )
    writer.writeheader()
    writer.writerows(stations)

print("Stations marked DC:", len(stations))
print()

for station in stations:
    print(
        station["station_id"],
        "|",
        station["name"],
        "|",
        station["latitude"],
        station["longitude"],
    )

print()
print("Saved:", output_file)
print("Rainfall availability has not yet been checked.")