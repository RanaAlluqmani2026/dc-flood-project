import csv
from pathlib import Path
from urllib.request import urlopen

import h5py
import truststore

truststore.inject_into_ssl()

project_dir = Path(__file__).resolve().parent
reports_dir = project_dir / "reports"

# Read the station candidates found in the previous step.
with (reports_dir / "dc_station_candidates.csv").open(
    newline="", encoding="utf-8"
) as file:
    stations = {
        row["station_id"]: row
        for row in csv.DictReader(file)
    }

# Get the years covered by our flood-event records.
with h5py.File(project_dir / "prism_dc_events.h5", "r") as h5:
    starts = h5["events/start_est"].asstr()[:]
    ends = h5["events/end_est"].asstr()[:]

first_event_year = min(int(value[:4]) for value in starts)
last_event_year = max(int(value[:4]) for value in ends)

url = (
    "https://www.ncei.noaa.gov/pub/data/ghcn/daily/"
    "ghcnd-inventory.txt"
)

print("Checking rainfall inventory...", flush=True)
results = []

# Read the inventory line by line.
with urlopen(url, timeout=120) as response:
    for raw_line in response:
        line = raw_line.decode("utf-8")

        station_id = line[0:11].strip()
        element = line[31:35].strip()

        if station_id not in stations or element != "PRCP":
            continue

        first_year = int(line[36:40])
        last_year = int(line[41:45])

        overlaps = (
            first_year <= last_event_year
            and last_year >= first_event_year
        )

        station = stations[station_id]

        results.append({
            **station,
            "variable": "PRCP",
            "first_inventory_year": first_year,
            "last_inventory_year": last_year,
            "overlaps_event_years": overlaps,
        })

output_file = reports_dir / "dc_station_rainfall_inventory.csv"

fieldnames = [
    "station_id", "name", "latitude", "longitude",
    "elevation_m", "state", "variable",
    "first_inventory_year", "last_inventory_year",
    "overlaps_event_years",
]

with output_file.open("w", newline="", encoding="utf-8") as file:
    writer = csv.DictWriter(file, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(results)

print("Flood-event years:", first_event_year, "-", last_event_year)
print("Candidates with PRCP inventory:", len(results))
print()
print("Stations whose rainfall record overlaps our event years:")

for row in results:
    if row["overlaps_event_years"]:
        print(
            row["station_id"],
            "|", row["name"],
            "|", row["first_inventory_year"],
            "-", row["last_inventory_year"],
        )

print()
print("Saved:", output_file)
print("Inventory years do not guarantee complete daily records.")