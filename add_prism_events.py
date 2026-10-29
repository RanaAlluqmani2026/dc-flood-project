import csv
import shutil
from pathlib import Path

import h5py
import numpy as np

project_dir = Path(__file__).resolve().parent

source_file = project_dir / "prism_dc.h5"
mapping_file = project_dir / "prism_event_dates.csv"
output_file = project_dir / "prism_dc_events.h5"
temporary_file = project_dir / "prism_dc_events_building.h5"

if output_file.exists():
    raise FileExistsError(
        "prism_dc_events.h5 already exists. "
        "Rename it before running this script again."
    )

if temporary_file.exists():
    raise FileExistsError(
        "prism_dc_events_building.h5 already exists. "
        "Rename it before running this script again."
    )

# Read the event-to-PRISM mapping.
with mapping_file.open(newline="", encoding="utf-8-sig") as file:
    links = list(csv.DictReader(file))

if not links:
    raise ValueError("The event-date mapping is empty.")

# Collect the start and end times of each event.
events = {}

for row in links:
    event_id = int(row["event_id"])
    times = (
        row["event_start_est"],
        row["event_end_est"],
    )

    if event_id in events and events[event_id] != times:
        raise ValueError(f"Inconsistent times for event {event_id}.")

    events[event_id] = times

event_ids = sorted(events)

# Copy the rainfall file, then add the event information.
try:
    shutil.copyfile(source_file, temporary_file)

    with h5py.File(temporary_file, "a") as h5:
        dates = list(h5["dates"].asstr()[:])
        date_index = {
            date: index for index, date in enumerate(dates)
        }

        missing_dates = sorted({
            row["prism_date"]
            for row in links
            if row["prism_date"] not in date_index
        })

        if missing_dates:
            raise ValueError(
                f"Required dates are missing: {missing_dates}"
            )

        string_type = h5py.string_dtype(encoding="utf-8")

        event_group = h5.create_group("events")

        event_group.create_dataset(
            "event_id",
            data=np.array(event_ids, dtype="int32"),
        )

        event_group.create_dataset(
            "start_est",
            data=np.array(
                [events[event_id][0] for event_id in event_ids],
                dtype=object,
            ),
            dtype=string_type,
        )

        event_group.create_dataset(
            "end_est",
            data=np.array(
                [events[event_id][1] for event_id in event_ids],
                dtype=object,
            ),
            dtype=string_type,
        )

        event_group.attrs["time_zone"] = "Fixed EST, UTC-05:00"
        event_group.attrs["event_id_definition"] = (
            "One-based row number in DC_flood_times.csv"
        )

        mapping_group = h5.create_group("event_prism_mapping")

        mapping_group.create_dataset(
            "event_id",
            data=np.array(
                [int(row["event_id"]) for row in links],
                dtype="int32",
            ),
        )

        mapping_group.create_dataset(
            "prism_date",
            data=np.array(
                [row["prism_date"] for row in links],
                dtype=object,
            ),
            dtype=string_type,
        )

        mapping_group.create_dataset(
            "prism_date_index",
            data=np.array(
                [date_index[row["prism_date"]] for row in links],
                dtype="int32",
            ),
        )

        mapping_group.attrs["index_definition"] = (
            "Zero-based index into dates and precipitation_mm"
        )

        mapping_group.attrs["interval_convention"] = (
            "Positive-duration events use [start, end). "
            "Zero-duration events are treated as point timestamps. "
            "PRISM intervals use [07:00 EST, next-day 07:00 EST)."
        )

    # Reopen the saved file and verify its links.
    with h5py.File(temporary_file, "r") as h5:
        saved_dates = h5["dates"].asstr()[:]
        linked_dates = h5["event_prism_mapping/prism_date"].asstr()[:]
        indices = h5["event_prism_mapping/prism_date_index"][:]

        if not np.array_equal(saved_dates[indices], linked_dates):
            raise ValueError("Saved date links failed verification.")

        if len(h5["events/event_id"]) != len(events):
            raise ValueError("Saved event count failed verification.")

    temporary_file.replace(output_file)

except Exception:
    if temporary_file.exists():
        temporary_file.unlink()
    raise

print("Finished! Created:", output_file.name)
print("Flood-event records:", len(events))
print("Event-to-PRISM links:", len(links))
print("Saved date links verified successfully.")
print("Original rainfall file preserved:", source_file.name)