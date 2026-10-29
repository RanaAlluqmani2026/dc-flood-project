import csv
from datetime import datetime
from pathlib import Path

file_path = Path(__file__).parent / "DC_flood_times.csv"
events = []

with file_path.open(newline="", encoding="utf-8-sig") as file:
    reader = csv.DictReader(file)

    for row in reader:
        start = datetime.strptime(
            f"{row['begin_date']} {row['begin_time']}",
            "%Y-%m-%d %H:%M"
        )
        end = datetime.strptime(
            f"{row['end_date']} {row['end_time']}",
            "%Y-%m-%d %H:%M"
        )
        events.append((start, end))

print(f"Number of flood event records: {len(events)}")
print(f"Earliest start: {min(start for start, end in events)}")
print(f"Latest end: {max(end for start, end in events)}")
print(f"Events ending before they start: {sum(end < start for start, end in events)}")
print("Event times are in fixed EST (UTC-5), according to the instructor.")