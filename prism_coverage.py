import csv
from pathlib import Path

import h5py
import numpy as np

project_dir = Path(__file__).resolve().parent
reports_dir = project_dir / "reports"
reports_dir.mkdir(exist_ok=True)

# Read the dates required by our event-date mapping
with (project_dir / "prism_event_dates.csv").open(
    newline="", encoding="utf-8-sig"
) as file:
    links = list(csv.DictReader(file))

required_dates = {row["prism_date"].strip() for row in links}

# Examine every daily grid in the HDF5 file
with h5py.File(project_dir / "prism_dc_events.h5", "r") as h5:
    dates = list(h5["dates"].asstr()[:])
    rainfall = h5["precipitation_mm"]

    if len(dates) != len(set(dates)):
        raise ValueError("Duplicate dates found in the HDF5 file.")

    if rainfall.shape != (
        len(dates),
        len(h5["latitude"]),
        len(h5["longitude"]),
    ):
        raise ValueError("Data dimensions do not match the coordinates.")

    results = []

    for index, date in enumerate(dates):
        grid = rainfall[index]
        valid = np.isfinite(grid)
        values = grid[valid]

        results.append({
            "prism_date": date,
            "total_cells": grid.size,
            "valid_cells": int(valid.sum()),
            "missing_or_nonfinite_cells": int((~valid).sum()),
            "valid_percent": round(100 * valid.sum() / grid.size, 2),
            "negative_cells": int((values < 0).sum()),
            "minimum_mm": round(float(values.min()), 3) if values.size else "",
            "mean_mm": round(float(values.mean()), 3) if values.size else "",
            "maximum_mm": round(float(values.max()), 3) if values.size else "",
        })

available_dates = set(dates)
missing_dates = sorted(required_dates - available_dates)
extra_dates = sorted(available_dates - required_dates)

# Save a daily coverage and rainfall summary
daily_report = reports_dir / "prism_daily_coverage.csv"

with daily_report.open("w", newline="", encoding="utf-8") as file:
    writer = csv.DictWriter(file, fieldnames=list(results[0]))
    writer.writeheader()
    writer.writerows(results)

fully_valid_days = sum(
    row["missing_or_nonfinite_cells"] == 0 for row in results
)
negative_cells = sum(row["negative_cells"] for row in results)
covered_links = sum(
    row["prism_date"].strip() in available_dates for row in links
)

summary = [
    f"Required unique dates: {len(required_dates)}",
    f"Stored unique dates: {len(available_dates)}",
    f"Missing required dates: {len(missing_dates)}",
    f"Extra dates: {len(extra_dates)}",
    f"Event-date links with a stored grid: {covered_links}/{len(links)}",
    f"Days with all cells valid: {fully_valid_days}/{len(dates)}",
    f"Negative precipitation cells: {negative_cells}",
    f"Missing dates: {', '.join(missing_dates) or 'None'}",
    "",
    "Scope: rectangular area covering DC and surrounding locations.",
    "Daily mean is the mean across valid cells in this rectangle.",
    "It is not a mean restricted to the DC boundary.",
    "PRISM dates label 24-hour periods ending at 12:00 UTC.",
    "Daily totals do not isolate rainfall during flood-event hours.",
    "Date coverage is checked against prism_event_dates.csv.",
    "The event-to-PRISM date mapping requires a separate review.",
]

summary_report = reports_dir / "prism_coverage_summary.txt"
summary_report.write_text("\n".join(summary), encoding="utf-8")

print("\n".join(summary[:9]))
print()
print("Reports saved:")
print(daily_report)
print(summary_report)