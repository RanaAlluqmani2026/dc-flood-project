import csv
from pathlib import Path

import h5py
import numpy as np

project_dir = Path(__file__).resolve().parent
database = project_dir / "prism_dc_events.h5"

with (project_dir / "reports" / "selected_station_locations.csv").open(
    newline="", encoding="utf-8"
) as file:
    stations = [
        row for row in csv.DictReader(file)
        if row["inside_dc_coordinate_check"] == "True"
    ]

with (project_dir / "reports" / "station_download_log.csv").open(
    newline="", encoding="utf-8"
) as file:
    download_log = {
        row["station_id"]: row
        for row in csv.DictReader(file)
    }

# Validate and load all processed files before changing HDF5.
loaded = []

for station in stations:
    station_id = station["station_id"]
    csv_file = (
        project_dir / "station_processed"
        / f"{station_id}_precipitation.csv"
    )

    with csv_file.open(newline="", encoding="utf-8") as file:
        records = list(csv.DictReader(file))

    if not records:
        raise ValueError(f"No processed records: {station_id}")

    dates = [row["date_label"] for row in records]

    if dates != sorted(set(dates)):
        raise ValueError(f"Dates are duplicated or unsorted: {station_id}")

    loaded.append((station, records))

string_type = h5py.string_dtype(encoding="utf-8")

with h5py.File(database, "r+") as h5:
    if "stations" in h5 or "_stations_building" in h5:
        raise ValueError(
            "Station data already exist, or an earlier build is unfinished."
        )

    try:
        parent = h5.create_group("_stations_building")
        parent.attrs["source"] = "NOAA NCEI GHCN-Daily"
        parent.attrs["spatial_support"] = "Station point observations"

        for station, records in loaded:
            station_id = station["station_id"]
            group = parent.create_group(station_id)

            group.attrs["name"] = station["name"]
            group.attrs["latitude"] = float(station["latitude"])
            group.attrs["longitude"] = float(station["longitude"])
            group.attrs["elevation_m"] = float(station["elevation_m"])
            group.attrs["location_check"] = (
                "Catalog coordinates passed DC boundary check; "
                "historical moves and catalog datum not verified."
            )
            group.attrs["source_url"] = download_log[station_id]["source_url"]
            group.attrs["retrieved_utc"] = download_log[station_id]["retrieved_utc"]
            group.attrs["documentation_url"] = (
                "https://www.ncei.noaa.gov/pub/data/ghcn/daily/readme.txt"
            )
            group.attrs["temporal_resolution"] = "Daily precipitation records"
            group.attrs["time_semantics"] = (
                "Original date labels and observation-time strings preserved. "
                "No UTC conversion or exact interval alignment applied."
            )
            group.attrs["missing_dates"] = (
                "Dates absent from this series are missing, not zero rainfall."
            )

            text_columns = [
                "date_label",
                "measurement_flag",
                "quality_flag",
                "source_flag",
                "observation_time_hhmm",
            ]

            for column in text_columns:
                group.create_dataset(
                    column,
                    data=np.array(
                        [row[column] for row in records],
                        dtype=object,
                    ),
                    dtype=string_type,
                    compression="gzip",
                )

            rainfall = np.array([
                float(row["precipitation_mm"])
                if row["precipitation_mm"] else np.nan
                for row in records
            ], dtype="float32")

            values = group.create_dataset(
                "precipitation_mm",
                data=rainfall,
                compression="gzip",
            )
            values.attrs["units"] = "mm"
            values.attrs["processing"] = (
                "Raw PRCP divided by 10. Nonblank quality flags "
                "or negative raw values excluded as NaN."
            )
            values.attrs["trace"] = (
                "Trace flag retained separately. A stored zero with "
                "trace=True is not an exact zero."
            )

            group.create_dataset(
                "raw_prcp_tenths_mm",
                data=np.array(
                    [int(row["raw_prcp_tenths_mm"]) for row in records],
                    dtype="int32",
                ),
                compression="gzip",
            )

            for column in ["trace", "usable"]:
                group.create_dataset(
                    column,
                    data=np.array(
                        [row[column] == "True" for row in records],
                        dtype=bool,
                    ),
                    compression="gzip",
                )

            print(station_id, "| stored records:", len(records))

        h5.move("_stations_building", "stations")

    except Exception:
        if "_stations_building" in h5:
            del h5["_stations_building"]
        raise

print()
print("Finished! Station data added to:", database.name)
print("PRISM data and flood-event records preserved.")