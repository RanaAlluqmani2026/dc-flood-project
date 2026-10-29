import csv
import gzip
import io
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlopen

import truststore

truststore.inject_into_ssl()

project_dir = Path(__file__).resolve().parent
reports_dir = project_dir / "reports"
download_dir = project_dir / "station_downloads"
download_dir.mkdir(exist_ok=True)

with (reports_dir / "selected_station_locations.csv").open(
    newline="", encoding="utf-8"
) as file:
    stations = [
        row for row in csv.DictReader(file)
        if row["inside_dc_coordinate_check"] == "True"
    ]

if not stations:
    raise ValueError("No selected stations passed the DC boundary check.")

log = []

for station in stations:
    station_id = station["station_id"]
    url = (
        "https://www.ncei.noaa.gov/pub/data/ghcn/daily/"
        f"by_station/{station_id}.csv.gz"
    )

    print("Downloading:", station_id, flush=True)

    with urlopen(url, timeout=120) as response:
        compressed_data = response.read()

    # Validate the downloaded data before saving.
    text = gzip.decompress(compressed_data).decode("utf-8")
    rows = list(csv.reader(io.StringIO(text)))

    if not rows:
        raise ValueError(f"No records returned for {station_id}.")

    for row in rows:
        if len(row) < 7 or row[0] != station_id:
            raise ValueError(f"Unexpected file format for {station_id}.")

    rainfall_rows = [row for row in rows if row[2] == "PRCP"]

    if not rainfall_rows:
        raise ValueError(f"No precipitation records for {station_id}.")

    output_file = download_dir / f"{station_id}.csv.gz"
    output_file.write_bytes(compressed_data)

    log.append({
        "station_id": station_id,
        "source_url": url,
        "retrieved_utc": datetime.now(timezone.utc).isoformat(),
        "download_bytes": len(compressed_data),
        "precipitation_records": len(rainfall_rows),
        "first_prcp_date": min(row[1] for row in rainfall_rows),
        "last_prcp_date": max(row[1] for row in rainfall_rows),
    })

    print("Saved:", output_file.name)
    print("Precipitation records:", len(rainfall_rows))
    print()

log_file = reports_dir / "station_download_log.csv"

with log_file.open("w", newline="", encoding="utf-8") as file:
    writer = csv.DictWriter(file, fieldnames=list(log[0]))
    writer.writeheader()
    writer.writerows(log)

print("Downloads finished.")
print("Stations downloaded:", len(log))
print("Download log saved:", log_file)
print("Daily quality and observation times still require checking.")