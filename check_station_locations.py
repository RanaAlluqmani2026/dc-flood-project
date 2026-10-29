import csv
from pathlib import Path

import h5py
import numpy as np
from matplotlib.path import Path as PolygonPath

project_dir = Path(__file__).resolve().parent
reports_dir = project_dir / "reports"

selected_ids = {
    "US1DCDC0009",
    "US1DCDC0014",
}

with (reports_dir / "dc_station_rainfall_inventory.csv").open(
    newline="", encoding="utf-8"
) as file:
    stations = [
        row for row in csv.DictReader(file)
        if row["station_id"] in selected_ids
    ]

if len(stations) != len(selected_ids):
    raise ValueError("One or more selected stations were not found.")

with h5py.File(project_dir / "prism_dc_events.h5", "r") as h5:
    group = h5["dc_boundary"]
    rings = [group[name][:] for name in sorted(group.keys())]

results = []

for station in stations:
    point = (
        float(station["longitude"]),
        float(station["latitude"]),
    )

    # Odd-even rule supports outer rings and holes.
    inside = False

    for ring in rings:
        if PolygonPath(np.asarray(ring)).contains_point(point):
            inside = not inside

    results.append({
        **station,
        "inside_dc_coordinate_check": inside,
        "location_check_note": (
            "Catalog longitude/latitude checked against DC GIS boundary. "
            "Catalog datum and historical station moves require review."
        ),
    })

    print("Station:", station["station_id"])
    print("Name:", station["name"])
    print("Coordinates:", point)
    print("Inside DC boundary:", inside)
    print()

output_file = reports_dir / "selected_station_locations.csv"

with output_file.open("w", newline="", encoding="utf-8") as file:
    writer = csv.DictWriter(file, fieldnames=list(results[0]))
    writer.writeheader()
    writer.writerows(results)

print("Saved:", output_file)
print("This checks catalog locations, not historical station moves.")