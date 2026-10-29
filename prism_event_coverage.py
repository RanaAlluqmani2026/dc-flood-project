import csv
from pathlib import Path

import h5py
import numpy as np

project_dir = Path(__file__).resolve().parent
h5_file = project_dir / "prism_dc_events.h5"

reports_dir = project_dir / "reports"
reports_dir.mkdir(exist_ok=True)

output_file = reports_dir / "prism_event_coverage.csv"
results = []

with h5py.File(h5_file, "r") as h5:
    event_ids = h5["events/event_id"][:]
    starts = h5["events/start_est"].asstr()[:]
    ends = h5["events/end_est"].asstr()[:]

    dates = h5["dates"].asstr()[:]
    rainfall = h5["precipitation_mm"]

    mapping = h5["event_prism_mapping"]
    linked_ids = mapping["event_id"][:]
    linked_dates = mapping["prism_date"].asstr()[:]
    linked_indices = mapping["prism_date_index"][:]

    for event_id, start, end in zip(event_ids, starts, ends):
        selected = linked_ids == event_id
        requested_dates = sorted(set(linked_dates[selected]))

        # Check each date link against the stored rainfall array.
        date_to_index = {}

        for date, index in zip(
            linked_dates[selected],
            linked_indices[selected],
        ):
            index = int(index)

            if (
                0 <= index < len(dates)
                and index < rainfall.shape[0]
                and dates[index] == date
            ):
                date_to_index[date] = index

        total_cells = 0
        valid_cells = 0
        negative_cells = 0
        usable_days = 0
        complete_days = 0

        for date in requested_dates:
            if date not in date_to_index:
                continue

            grid = rainfall[date_to_index[date]]
            usable = np.isfinite(grid) & (grid >= 0)

            total_cells += grid.size
            valid_cells += int(usable.sum())
            negative_cells += int(
                (np.isfinite(grid) & (grid < 0)).sum()
            )

            usable_days += int(usable.any())
            complete_days += int(usable.all())

        required_days = len(requested_dates)
        stored_days = len(date_to_index)

        complete = (
            required_days > 0
            and stored_days == required_days
            and complete_days == required_days
        )

        results.append({
            "event_id": int(event_id),
            "source": "PRISM",
            "event_start_est": start,
            "event_end_est": end,
            "linked_prism_dates": ";".join(requested_dates),
            "required_days_from_mapping": required_days,
            "stored_days": stored_days,
            "days_with_usable_cells": usable_days,
            "days_with_all_cells_usable": complete_days,
            "missing_or_invalid_date_links": required_days - stored_days,
            "usable_cell_percent_of_stored_grids": (
                round(100 * valid_cells / total_cells, 2)
                if total_cells else ""
            ),
            "negative_cells": negative_cells,
            "coverage_status": (
                "complete" if complete else "incomplete"
            ),
        })

if not results:
    raise ValueError("No flood events were found.")

with output_file.open("w", newline="", encoding="utf-8") as file:
    writer = csv.DictWriter(
        file,
        fieldnames=list(results[0]),
    )
    writer.writeheader()
    writer.writerows(results)

complete_count = sum(
    row["coverage_status"] == "complete"
    for row in results
)

print("Report saved:", output_file)
print("Flood-event records:", len(results))
print("Events with complete linked daily grids:", complete_count)
print("Events with incomplete coverage:", len(results) - complete_count)
print()
print("Coverage is assessed against the saved event-date mapping.")
print("Spatial scope: DC and surrounding rectangular area.")
print("Complete daily grids do not provide event-hour rainfall totals.")