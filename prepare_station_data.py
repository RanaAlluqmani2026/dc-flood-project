import csv
import gzip
from datetime import datetime, timedelta
from pathlib import Path

import h5py

project_dir = Path(__file__).resolve().parent
download_dir = project_dir / "station_downloads"
processed_dir = project_dir / "station_processed"
processed_dir.mkdir(exist_ok=True)

with h5py.File(project_dir / "prism_dc_events.h5", "r") as h5:
    event_starts = h5["events/start_est"].asstr()[:]
    event_ends = h5["events/end_est"].asstr()[:]

# Keep a one-day calendar buffer around the full event period.
first_date = (
    min(datetime.strptime(value, "%Y-%m-%d %H:%M")
        for value in event_starts).date()
    - timedelta(days=1)
)
last_date = (
    max(datetime.strptime(value, "%Y-%m-%d %H:%M")
        for value in event_ends).date()
    + timedelta(days=1)
)

with (project_dir / "reports" / "selected_station_locations.csv").open(
    newline="", encoding="utf-8"
) as file:
    stations = [
        row for row in csv.DictReader(file)
        if row["inside_dc_coordinate_check"] == "True"
    ]

for station in stations:
    station_id = station["station_id"]
    input_file = download_dir / f"{station_id}.csv.gz"
    output_file = processed_dir / f"{station_id}_precipitation.csv"

    records = []
    seen_dates = set()

    with gzip.open(input_file, "rt", encoding="utf-8", newline="") as file:
        for row in csv.reader(file):
            if row[2] != "PRCP":
                continue

            date = datetime.strptime(row[1], "%Y%m%d").date()

            if not first_date <= date <= last_date:
                continue

            if date in seen_dates:
                raise ValueError(
                    f"Duplicate precipitation date: {station_id}, {date}"
                )
            seen_dates.add(date)

            raw_value = int(row[3])
            measurement_flag = row[4].strip()
            quality_flag = row[5].strip()
            source_flag = row[6].strip()
            observation_time = row[7].strip() if len(row) > 7 else ""

            usable = raw_value >= 0 and quality_flag == ""

            records.append({
                "station_id": station_id,
                "date_label": date.isoformat(),
                "raw_prcp_tenths_mm": raw_value,
                "precipitation_mm": raw_value / 10 if usable else "",
                "measurement_flag": measurement_flag,
                "quality_flag": quality_flag,
                "source_flag": source_flag,
                "observation_time_hhmm": observation_time,
                "trace": measurement_flag == "T",
                "usable": usable,
            })

    records.sort(key=lambda record: record["date_label"])

    if not records:
        raise ValueError(f"No records in the study period: {station_id}")

    with output_file.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)

    print("Station:", station_id)
    print("Records retained:", len(records))
    print("Usable records:", sum(record["usable"] for record in records))
    print("Excluded records:", sum(not record["usable"] for record in records))
    print("Trace records:", sum(record["trace"] for record in records))
    print("First date:", records[0]["date_label"])
    print("Last date:", records[-1]["date_label"])
    print("Saved:", output_file.name)
    print()

print("Finished preparing station precipitation.")
print("Missing dates were not replaced with zero.")
print("Trace flags were preserved; trace is not an exact zero.")
print("Observation-time zones and interval alignment still need review.")