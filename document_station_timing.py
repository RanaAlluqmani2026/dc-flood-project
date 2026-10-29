from pathlib import Path

import h5py

project_dir = Path(__file__).resolve().parent
reports_dir = project_dir / "reports"
reports_dir.mkdir(exist_ok=True)

notes = """Station time interpretation

Sources reviewed:
https://www.ncei.noaa.gov/pub/data/ghcn/daily/readme-by_station.txt
https://cocorahs.blogspot.com/2020/06/the-importance-of-observation-time.html

NOAA defines OBS-TIME as an HHMM observation-time field and states
that it is populated from the HOMR station-history database.
The file description does not explicitly specify a UTC offset
or daylight-saving convention for every imported record.

CoCoRaHS guidance describes local observation times and seasonal
clock changes. Observers may report at different times.
Observation time is the measurement time, not data-entry time.

This general guidance does not independently establish how each
historical OBS-TIME value was represented in the downloaded files.

Project decision:
Preserve original date labels, HHMM times, and quality flags.
Do not assign unverified UTC offsets or fabricate interval starts.
Do not assume identical station and PRISM accumulation intervals.
Do not calculate flood-hour rainfall totals from daily records.

Station plots and coverage reports use a calendar-date window:
event dates plus three days before and after.
This is a contextual retrieval window, not proof of exact temporal
overlap or complete rainfall measurement during the flood.

Limitation:
Record-specific UTC observation instants and accumulation-period
boundaries remain unverified. Exact temporal comparison would require
additional source metadata or original observation reports.
"""

report_file = reports_dir / "station_time_interpretation.txt"
report_file.write_text(notes, encoding="utf-8")

with h5py.File(project_dir / "prism_dc_events.h5", "r+") as h5:
    stations = h5["stations"]

    stations.attrs["time_review_sources"] = (
        "https://www.ncei.noaa.gov/pub/data/ghcn/daily/"
        "readme-by_station.txt ; "
        "https://cocorahs.blogspot.com/2020/06/"
        "the-importance-of-observation-time.html"
    )

    stations.attrs["time_review_conclusion"] = (
        "Original date labels and HHMM observation times preserved. "
        "Record-specific UTC offsets and accumulation boundaries "
        "not verified; no exact temporal equivalence with PRISM claimed."
    )

    stations.attrs["event_window_method"] = (
        "Original station date labels within event calendar dates "
        "plus three days before and after; contextual availability only."
    )

print("Saved:", report_file)
print("Time-interpretation notes added to HDF5.")
print("Original observations were not changed.")