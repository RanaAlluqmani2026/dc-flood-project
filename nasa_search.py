import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

import truststore

truststore.inject_into_ssl()

project_dir = Path(__file__).resolve().parent
reports_dir = project_dir / "reports"
reports_dir.mkdir(exist_ok=True)

# Event 124: search nearby dates for contextual satellite observations.
# These dates do not imply that a scene overlaps the flood hours.
parameters = {
    "short_name": "OPERA_L3_DSWX-HLS_V1",
    "bounding_box": "-77.15,38.78,-76.90,39.00",
    "temporal": "2025-07-10T00:00:00Z,2025-07-16T23:59:59Z",
    "page_size": 100,
}

search_url = (
    "https://cmr.earthdata.nasa.gov/search/granules.json?"
    + urlencode(parameters)
)

print("Searching NASA's catalog...")

with urlopen(search_url, timeout=120) as response:
    catalog = json.load(response)

entries = catalog["feed"].get("entry", [])

if len(entries) >= 100:
    raise RuntimeError("Search may require pagination; narrow the dates.")

retrieved_utc = datetime.now(timezone.utc).isoformat()

# Preserve the catalog response and exact search for reproducibility.
with (reports_dir / "nasa_search_event_124.json").open(
    "w", encoding="utf-8"
) as file:
    json.dump(
        {
            "event_id": 124,
            "retrieved_utc": retrieved_utc,
            "search_url": search_url,
            "catalog_response": catalog,
        },
        file,
        indent=2,
    )

output_file = reports_dir / "nasa_candidates_event_124.csv"

with output_file.open("w", newline="", encoding="utf-8") as file:
    writer = csv.DictWriter(
        file,
        fieldnames=[
            "event_id",
            "scene_id",
            "time_start_utc",
            "time_end_utc",
        ],
    )
    writer.writeheader()

    for entry in entries:
        writer.writerow({
            "event_id": 124,
            "scene_id": entry.get("title", ""),
            "time_start_utc": entry.get("time_start", ""),
            "time_end_utc": entry.get("time_end", ""),
        })

print(f"Candidate scenes: {len(entries)}")
print(f"Saved: {output_file.name}")
print("Catalog matches only; cloud cover and DC coverage need review.")