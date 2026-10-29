from datetime import date, timedelta
from pathlib import Path

import h5py
import numpy as np

DATABASE = Path(__file__).resolve().parent / "prism_dc_events.h5"


def list_stations():
    """List stored stations and their metadata."""
    results = []

    with h5py.File(DATABASE, "r") as h5:
        for station_id in sorted(h5["stations"].keys()):
            group = h5["stations"][station_id]
            labels = group["date_label"].asstr()[:]

            results.append({
                "station_id": station_id,
                "name": group.attrs["name"],
                "latitude": float(group.attrs["latitude"]),
                "longitude": float(group.attrs["longitude"]),
                "first_stored_date": labels[0],
                "last_stored_date": labels[-1],
                "stored_records": len(labels),
                "units": group["precipitation_mm"].attrs["units"],
                "time_semantics": group.attrs["time_semantics"],
            })

    return results


def get_station_window(
    event_id,
    station_id,
    start_date,
    end_date,
):
    """Retrieve an inclusive window of original station date labels.

    The event ID provides context. Dates do not establish exact
    overlap between station accumulation intervals and flood hours.
    """
    first = date.fromisoformat(start_date)
    last = date.fromisoformat(end_date)

    if last < first:
        raise ValueError("End date must not precede start date.")

    with h5py.File(DATABASE, "r") as h5:
        ids = h5["events/event_id"][:]
        positions = np.flatnonzero(ids == event_id)

        if len(positions) == 0:
            raise ValueError(f"Unknown event ID: {event_id}")

        if station_id not in h5["stations"]:
            raise ValueError(f"Unknown station: {station_id}")

        position = int(positions[0])
        group = h5["stations"][station_id]

        labels = group["date_label"].asstr()[:]
        lookup = {
            label: index for index, label in enumerate(labels)
        }

        values = group["precipitation_mm"][:]
        times = group["observation_time_hhmm"].asstr()[:]
        quality = group["quality_flag"].asstr()[:]
        traces = group["trace"][:]

        records = []
        current = first

        while current <= last:
            label = current.isoformat()
            index = lookup.get(label)

            if index is None:
                record = {
                    "date_label": label,
                    "precipitation_mm": np.nan,
                    "observation_time_hhmm": "",
                    "quality_flag": "",
                    "trace": False,
                    "status": "missing_record",
                }
            else:
                value = float(values[index])

                record = {
                    "date_label": label,
                    "precipitation_mm": value,
                    "observation_time_hhmm": times[index],
                    "quality_flag": quality[index],
                    "trace": bool(traces[index]),
                    "status": (
                        "usable" if np.isfinite(value)
                        else "excluded_record"
                    ),
                }

            records.append(record)
            current += timedelta(days=1)

        return {
            "event_id": event_id,
            "event_start_est": h5["events/start_est"].asstr()[position],
            "event_end_est": h5["events/end_est"].asstr()[position],
            "station_id": station_id,
            "station_name": group.attrs["name"],
            "units": group["precipitation_mm"].attrs["units"],
            "time_semantics": group.attrs["time_semantics"],
            "records": records,
        }


if __name__ == "__main__":
    print("AVAILABLE STATIONS")
    for station in list_stations():
        print(
            station["station_id"],
            "|", station["name"],
            "|", station["first_stored_date"],
            "to", station["last_stored_date"],
        )

    example = get_station_window(
        event_id=71,
        station_id="US1DCDC0014",
        start_date="2016-07-16",
        end_date="2016-07-23",
    )

    print()
    print("EXAMPLE: event", example["event_id"])
    print("Station:", example["station_name"])
    print("Units:", example["units"])

    for record in example["records"]:
        print(
            record["date_label"],
            "|", record["precipitation_mm"],
            "| observation:", record["observation_time_hhmm"],
            "|", record["status"],
            "| trace:", record["trace"],
        )

    print()
    print("Original observation times are shown without UTC conversion.")
    print("Missing and excluded records remain NaN, not zero.")