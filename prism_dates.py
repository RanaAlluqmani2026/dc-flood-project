import csv
from datetime import datetime, timedelta
from pathlib import Path

project_dir = Path(__file__).resolve().parent
input_file = project_dir / "DC_flood_times.csv"
output_file = project_dir / "prism_event_dates.csv"


def prism_date_for_time(event_time):
    """Return the PRISM date for a fixed-EST timestamp.

    A PRISM interval starts at 07:00 EST and ends at 07:00 EST
    the following day. Its label is the ending date.

    The starting instant is included; the ending instant is excluded.
    """
    boundary = event_time.replace(
        hour=7,
        minute=0,
        second=0,
        microsecond=0,
    )

    if event_time < boundary:
        return event_time.date()

    return event_time.date() + timedelta(days=1)


rows = []
all_dates = set()
event_count = 0

with input_file.open(newline="", encoding="utf-8-sig") as file:
    reader = csv.DictReader(file)

    for event_id, event in enumerate(reader, start=1):
        event_count += 1

        start = datetime.strptime(
            f"{event['begin_date']} {event['begin_time']}",
            "%Y-%m-%d %H:%M",
        )

        end = datetime.strptime(
            f"{event['end_date']} {event['end_time']}",
            "%Y-%m-%d %H:%M",
        )

        if end < start:
            raise ValueError(
                f"Event {event_id} ends before it starts."
            )

        first_date = prism_date_for_time(start)

        # Select intervals that overlap the event's duration.
        # If the event ends exactly at 07:00, do not add
        # the new interval beginning at that instant.
        if end > start:
            last_date = prism_date_for_time(
                end - timedelta(microseconds=1)
            )
        else:
            # Treat zero-duration records as point timestamps.
            last_date = first_date

        current_date = first_date

        while current_date <= last_date:
            rows.append({
                "event_id": event_id,
                "event_start_est": start.strftime("%Y-%m-%d %H:%M"),
                "event_end_est": end.strftime("%Y-%m-%d %H:%M"),
                "prism_date": current_date.isoformat(),
            })

            all_dates.add(current_date)
            current_date += timedelta(days=1)

if event_count == 0:
    raise ValueError("The flood-events file contains no records.")

with output_file.open("w", newline="", encoding="utf-8") as file:
    writer = csv.DictWriter(
        file,
        fieldnames=[
            "event_id",
            "event_start_est",
            "event_end_est",
            "prism_date",
        ],
    )

    writer.writeheader()
    writer.writerows(rows)

print(f"Flood-event records: {event_count}")
print(f"Event-to-PRISM date entries: {len(rows)}")
print(f"Unique PRISM dates needed: {len(all_dates)}")
print(f"Saved: {output_file.name}")