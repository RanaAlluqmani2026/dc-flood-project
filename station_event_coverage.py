import csv
from pathlib import Path

import h5py
import numpy as np

from plot_station_event import get_station_series

project_dir = Path(__file__).resolve().parent
database = project_dir / "prism_dc_events.h5"
reports_dir = project_dir / "reports"
reports_dir.mkdir(exist_ok=True)


def station_event_coverage(buffer_days=3):
    """Assess availability by original station date labels."""
    with h5py.File(database, "r") as h5:
        event_ids = h5["events/event_id"][:]
        station_ids = sorted(h5["stations"].keys())

    results = []

    for event_id in event_ids:
        for station_id in station_ids:
            series = get_station_series(
                int(event_id),
                station_id,
                buffer_days=buffer_days,
            )

            values = series["values"]
            usable = np.isfinite(values)
            expected = len(values)
            available = int(usable.sum())

            if available == 0:
                status = "no_usable_records"
            elif available == expected:
                status = "complete_date_label_window"
            else:
                status = "partial_date_label_window"

            results.append({
                "event_id": int(event_id),
                "station_id": station_id,
                "station_name": series["name"],
                "event_start_est": series["start_est"],
                "event_end_est": series["end_est"],
                "buffer_days": buffer_days,
                "window_first_date": series["days"][0].isoformat(),
                "window_last_date": series["days"][-1].isoformat(),
                "expected_date_labels": expected,
                "usable_date_labels": available,
                "missing_or_excluded_date_labels": expected - available,
                "usable_percent": round(100 * available / expected, 2),
                "usable_trace_records": int(
                    (series["trace"] & usable).sum()
                ),
                "status": status,
            })

    return results


if __name__ == "__main__":
    results = station_event_coverage()

    output_file = reports_dir / "station_event_coverage.csv"

    with output_file.open(
        "w", newline="", encoding="utf-8"
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=list(results[0]),
        )
        writer.writeheader()
        writer.writerows(results)

    all_events = {row["event_id"] for row in results}
    events_with_records = {
        row["event_id"]
        for row in results
        if row["usable_date_labels"] > 0
    }

    summary = [
        f"Flood-event records: {len(all_events)}",
        f"Stations: {len({row['station_id'] for row in results})}",
        f"Event-station combinations: {len(results)}",
        (
            "Events with at least one usable station record "
            f"in the buffered window: {len(events_with_records)}"
        ),
        (
            "Events without usable station records "
            f"in the buffered window: "
            f"{len(all_events - events_with_records)}"
        ),
        "",
        "Window: event calendar dates plus 3 days before and after.",
        "Counts use original station date labels.",
        "Missing dates and excluded observations are not zero rainfall.",
        "This does not establish exact accumulation-interval overlap",
        "with flood hours or temporal equivalence with PRISM.",
    ]

    summary_file = reports_dir / "station_event_coverage_summary.txt"
    summary_file.write_text(
        "\n".join(summary),
        encoding="utf-8",
    )

    print("\n".join(summary))
    print()
    print("Saved:", output_file)
    print("Saved:", summary_file)