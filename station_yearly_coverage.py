import calendar
import csv
from datetime import date, datetime, timedelta
from pathlib import Path

import h5py
import numpy as np

project_dir = Path(__file__).resolve().parent
reports_dir = project_dir / "reports"
reports_dir.mkdir(exist_ok=True)

results = []

with h5py.File(project_dir / "prism_dc_events.h5", "r") as h5:
    starts = h5["events/start_est"].asstr()[:]
    ends = h5["events/end_est"].asstr()[:]

    first_date = min(
        datetime.strptime(value, "%Y-%m-%d %H:%M").date()
        for value in starts
    ) - timedelta(days=1)

    last_date = max(
        datetime.strptime(value, "%Y-%m-%d %H:%M").date()
        for value in ends
    ) + timedelta(days=1)

    for station_id in sorted(h5["stations"].keys()):
        group = h5["stations"][station_id]
        labels = group["date_label"].asstr()[:]
        values = group["precipitation_mm"][:]
        trace = group["trace"][:]

        observed_dates = [
            date.fromisoformat(label) for label in labels
        ]

        print("Station:", station_id)

        for year in range(first_date.year, last_date.year + 1):
            period_start = max(first_date, date(year, 1, 1))
            period_end = min(
                last_date,
                date(year, 12, 31),
            )

            expected_days = (period_end - period_start).days + 1

            selected = np.array([
                period_start <= day <= period_end
                for day in observed_dates
            ], dtype=bool)

            available = int(selected.sum())
            usable = int(np.isfinite(values[selected]).sum())

            results.append({
                "station_id": station_id,
                "station_name": group.attrs["name"],
                "year": year,
                "period_start": period_start.isoformat(),
                "period_end": period_end.isoformat(),
                "expected_calendar_days": expected_days,
                "recorded_days": available,
                "usable_days": usable,
                "excluded_recorded_days": available - usable,
                "days_without_record": expected_days - available,
                "usable_percent": round(
                    100 * usable / expected_days, 2
                ),
                "trace_records": int(trace[selected].sum()),
            })

        print("Stored records:", len(labels))
        print("Usable records:", int(np.isfinite(values).sum()))
        print()

output_file = reports_dir / "station_yearly_coverage.csv"

with output_file.open("w", newline="", encoding="utf-8") as file:
    writer = csv.DictWriter(
        file,
        fieldnames=list(results[0]),
    )
    writer.writeheader()
    writer.writerows(results)

print("Saved:", output_file)
print("Rows in report:", len(results))
print()
print("Expected days cover the study period, including years")
print("before these stations had records.")
print("Missing records do not mean zero rainfall.")
print("This report measures date-label availability, not exact")
print("overlap of station accumulation intervals with flood hours.")