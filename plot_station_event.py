from datetime import date, datetime, timedelta
from pathlib import Path

import h5py
import matplotlib.pyplot as plt
import numpy as np

project_dir = Path(__file__).resolve().parent
database = project_dir / "prism_dc_events.h5"
figures_dir = project_dir / "figures"
figures_dir.mkdir(exist_ok=True)


def get_station_series(event_id, station_id, buffer_days=3):
    """Read daily date labels around an event; preserve missing days."""
    with h5py.File(database, "r") as h5:
        ids = h5["events/event_id"][:]
        matches = np.flatnonzero(ids == event_id)

        if len(matches) == 0:
            raise ValueError("Unknown event ID.")

        position = int(matches[0])
        start = h5["events/start_est"].asstr()[position]
        end = h5["events/end_est"].asstr()[position]

        first = datetime.strptime(start, "%Y-%m-%d %H:%M").date()
        last = datetime.strptime(end, "%Y-%m-%d %H:%M").date()
        first -= timedelta(days=buffer_days)
        last += timedelta(days=buffer_days)

        group = h5["stations"][station_id]
        labels = group["date_label"].asstr()[:]
        rainfall = group["precipitation_mm"][:]
        trace_flags = group["trace"][:]

        lookup = {
            label: (value, trace)
            for label, value, trace in zip(
                labels, rainfall, trace_flags
            )
        }

        days = [
            first + timedelta(days=offset)
            for offset in range((last - first).days + 1)
        ]

        values = np.array([
            lookup.get(day.isoformat(), (np.nan, False))[0]
            for day in days
        ])

        traces = np.array([
            lookup.get(day.isoformat(), (np.nan, False))[1]
            for day in days
        ])

        return {
            "days": days,
            "values": values,
            "trace": traces,
            "name": group.attrs["name"],
            "start_est": start,
            "end_est": end,
        }


def plot_station_event(event_id):
    with h5py.File(database, "r") as h5:
        station_ids = sorted(h5["stations"].keys())

    fig, axes = plt.subplots(
        len(station_ids),
        1,
        figsize=(10, 3.5 * len(station_ids)),
        squeeze=False,
        layout="constrained",
    )

    for ax, station_id in zip(axes.flat, station_ids):
        series = get_station_series(event_id, station_id)
        days = series["days"]
        values = series["values"]
        usable = np.isfinite(values)

        ax.bar(
            np.array(days)[usable],
            values[usable],
            color="steelblue",
            label="Daily precipitation",
        )

        missing = ~usable
        if missing.any():
            ax.scatter(
                np.array(days)[missing],
                np.zeros(int(missing.sum())),
                marker="x",
                color="red",
                label="Missing or excluded",
                zorder=3,
            )

        trace = series["trace"] & usable
        if trace.any():
            ax.scatter(
                np.array(days)[trace],
                values[trace],
                marker="^",
                color="darkorange",
                label="Trace (not exact zero)",
                zorder=4,
            )

        ax.set_title(f"{station_id} — {series['name']}")
        ax.set_ylabel("Precipitation (mm)")
        ax.set_xlabel(
            "Original station date label; accumulation times not aligned"
        )
        ax.set_ylim(bottom=-1)
        ax.grid(axis="y", alpha=0.25)
        ax.legend(fontsize=8)
        ax.tick_params(axis="x", rotation=35)

        print(station_id, "| usable days:", int(usable.sum()), "/", len(days))

    fig.suptitle(
        f"Station observations around flood event {event_id}\n"
        f"Event: {series['start_est']} to {series['end_est']} (fixed EST)\n"
        "Three-day calendar buffer; values are not event-hour totals",
        fontsize=11,
    )

    output = figures_dir / f"station_event_{event_id:03d}.png"
    fig.savefig(output, dpi=200)
    print("Saved:", output)
    plt.show()


if __name__ == "__main__":
    # Choose an event with the most usable nearby daily observations
    # so the demonstration contains data rather than only gaps.
    with h5py.File(database, "r") as h5:
        event_ids = h5["events/event_id"][:]
        station_ids = sorted(h5["stations"].keys())

    best_event = None
    best_score = -1

    for event_id in event_ids:
        score = sum(
            int(np.isfinite(
                get_station_series(int(event_id), station_id)["values"]
            ).sum())
            for station_id in station_ids
        )

        if score > best_score:
            best_event = int(event_id)
            best_score = score

    print("Demonstration event selected:", best_event)
    plot_station_event(best_event)