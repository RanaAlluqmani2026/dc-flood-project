from pathlib import Path

import h5py
import numpy as np

DATABASE = Path(__file__).resolve().parent / "prism_dc_events.h5"


def list_events():
    """Return the available flood events from HDF5."""
    with h5py.File(DATABASE, "r") as h5:
        ids = h5["events/event_id"][:]
        starts = h5["events/start_est"].asstr()[:]
        ends = h5["events/end_est"].asstr()[:]

    return [
        {
            "event_id": int(event_id),
            "start_est": start,
            "end_est": end,
        }
        for event_id, start, end in zip(ids, starts, ends)
    ]


def describe_prism():
    """Return source, variable, dates, coordinates, and metadata."""
    with h5py.File(DATABASE, "r") as h5:
        dates = list(h5["dates"].asstr()[:])
        latitude = h5["latitude"][:]
        longitude = h5["longitude"][:]

        return {
            "source": h5.attrs["source"],
            "variable": "precipitation_mm",
            "units": h5["precipitation_mm"].attrs["units"],
            "crs": h5.attrs["crs"],
            "time_interval": h5.attrs["prism_day"],
            "number_of_dates": len(dates),
            "first_date": dates[0],
            "last_date": dates[-1],
            "shape": h5["precipitation_mm"].shape,
            "latitude_spacing_degrees": float(
                abs(latitude[1] - latitude[0])
            ),
            "longitude_spacing_degrees": float(
                abs(longitude[1] - longitude[0])
            ),
            "available_dates": dates,
        }


def event_dates(event_id):
    """Return PRISM dates linked to a selected flood event."""
    with h5py.File(DATABASE, "r") as h5:
        if event_id not in h5["events/event_id"][:]:
            raise ValueError(f"Unknown event ID: {event_id}")

        mapping = h5["event_prism_mapping"]
        selected = mapping["event_id"][:] == event_id

        return sorted(set(
            mapping["prism_date"].asstr()[:][selected]
        ))


def get_raster(event_id, date, source="PRISM"):
    """Return a linked raster, coordinates, units, and CRS."""
    if source != "PRISM":
        raise ValueError("This function currently supports PRISM only.")

    if date not in event_dates(event_id):
        raise ValueError(
            f"Date {date} is not linked to event {event_id}."
        )

    with h5py.File(DATABASE, "r") as h5:
        dates = list(h5["dates"].asstr()[:])
        index = dates.index(date)

        return {
            "event_id": event_id,
            "source": source,
            "date": date,
            "values": h5["precipitation_mm"][index],
            "latitude": h5["latitude"][:],
            "longitude": h5["longitude"][:],
            "units": h5["precipitation_mm"].attrs["units"],
            "crs": h5.attrs["crs"],
            "interval": h5.attrs["prism_day"],
        }


if __name__ == "__main__":
    events = list_events()
    info = describe_prism()

    print("Available flood-event records:", len(events))
    print("Source:", info["source"])
    print("Variable:", info["variable"])
    print("Units:", info["units"])
    print("CRS:", info["crs"])
    print("Stored dates:", info["number_of_dates"])
    print("First and last dates:", info["first_date"], info["last_date"])
    print("Note: only selected event-related dates are stored.")
    print()

    print("First five events:")
    for event in events[:5]:
        print(event)

    # Demonstrate retrieving the first event's first daily raster.
    example_id = events[0]["event_id"]
    example_date = event_dates(example_id)[0]
    raster = get_raster(example_id, example_date)

    print()
    print("Example event:", example_id)
    print("Retrieved PRISM date:", example_date)
    print("Raster shape:", raster["values"].shape)
    print("Minimum:", float(np.nanmin(raster["values"])), raster["units"])
    print("Maximum:", float(np.nanmax(raster["values"])), raster["units"])
    print("Data retrieved directly from HDF5.")