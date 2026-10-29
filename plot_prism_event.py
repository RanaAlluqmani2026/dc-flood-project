import math
from pathlib import Path

import h5py
import matplotlib.pyplot as plt
import numpy as np

project_dir = Path(__file__).resolve().parent
file_path = project_dir / "prism_dc_events.h5"

figures_dir = project_dir / "figures"
figures_dir.mkdir(exist_ok=True)


def plot_event(event_id):
    """Plot an event's daily PRISM grids and DC boundary from HDF5."""
    with h5py.File(file_path, "r") as h5:
        event_ids = h5["events/event_id"][:]
        positions = np.flatnonzero(event_ids == event_id)

        if len(positions) == 0:
            raise ValueError(
                f"Event {event_id} is not available."
            )

        position = int(positions[0])
        start = h5["events/start_est"].asstr()[position]
        end = h5["events/end_est"].asstr()[position]

        mapping = h5["event_prism_mapping"]
        selected = mapping["event_id"][:] == event_id
        indices = np.unique(
            mapping["prism_date_index"][:][selected]
        )

        dates = h5["dates"].asstr()[:]
        latitude = h5["latitude"][:]
        longitude = h5["longitude"][:]

        grids = [
            h5["precipitation_mm"][int(index)]
            for index in indices
        ]
        selected_dates = [
            dates[int(index)] for index in indices
        ]

        boundary_group = h5["dc_boundary"]

        if boundary_group.attrs["crs"] != h5.attrs["crs"]:
            raise ValueError("Boundary and rainfall CRS differ.")

        rings = [
            boundary_group[name][:]
            for name in sorted(boundary_group.keys())
        ]

    if not grids:
        raise ValueError("No PRISM grids are linked to this event.")

    maximum = max(
        max(float(np.nanmax(grid)) for grid in grids),
        1.0,
    )

    columns = min(3, len(grids))
    rows = math.ceil(len(grids) / columns)

    fig, axes = plt.subplots(
        rows,
        columns,
        figsize=(6 * columns, 5.5 * rows),
        squeeze=False,
        layout="constrained",
    )

    used_axes = []

    for ax, date, grid in zip(
        axes.flat, selected_dates, grids
    ):
        image = ax.pcolormesh(
            longitude,
            latitude,
            grid,
            shading="nearest",
            cmap="Blues",
            vmin=0,
            vmax=maximum,
        )

        # Draw the DC boundary stored in HDF5.
        for ring_index, ring in enumerate(rings):
            ax.plot(
                ring[:, 0],
                ring[:, 1],
                color="black",
                linewidth=1.5,
                label="DC boundary" if ring_index == 0 else None,
            )

        ax.set_aspect(
            1 / np.cos(np.deg2rad(latitude.mean()))
        )
        ax.set_title(f"PRISM date: {date}")
        ax.set_xlabel("Longitude (NAD83)")
        ax.set_ylabel("Latitude (NAD83)")
        ax.legend(loc="lower left", fontsize=8)
        used_axes.append(ax)

    for ax in list(axes.flat)[len(grids):]:
        ax.set_visible(False)

    fig.colorbar(
        image,
        ax=used_axes,
        label="Daily precipitation (mm)",
        shrink=0.8,
    )

    fig.suptitle(
        f"Flood event {event_id}\n"
        f"{start} to {end} (fixed EST)\n"
        "Full PRISM daily totals; DC boundary: DC GIS",
        fontsize=11,
    )

    output_file = (
        figures_dir / f"prism_event_{event_id:03d}_dc.png"
    )
    fig.savefig(output_file, dpi=200)

    print("Map saved:", output_file)
    print("Linked PRISM dates:", ", ".join(selected_dates))
    print("Rainfall and boundary were read directly from HDF5.")
    print("Daily totals do not isolate rainfall during event hours.")

    plt.show()


if __name__ == "__main__":
    try:
        requested_id = int(
            input("Enter flood event ID (1-125): ")
        )
        plot_event(requested_id)
    except ValueError as error:
        print(error)