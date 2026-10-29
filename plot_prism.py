from pathlib import Path

import h5py
import matplotlib.pyplot as plt

project_dir = Path(__file__).resolve().parent
file_path = project_dir / "prism_dc.h5"

# Ask for the date to display
requested_date = input("Enter a PRISM date (YYYY-MM-DD): ").strip()

with h5py.File(file_path, "r") as h5:
    dates = h5["dates"].asstr()[:]

    if requested_date not in dates:
        print("This date is not available in the file.")
        print("Example of an available date:", dates[0])
    else:
        index = list(dates).index(requested_date)

        rainfall = h5["precipitation_mm"][index]
        latitude = h5["latitude"][:]
        longitude = h5["longitude"][:]

        fig, ax = plt.subplots(figsize=(8, 6))

        grid = ax.pcolormesh(
            longitude,
            latitude,
            rainfall,
            shading="nearest",
            cmap="Blues",
            vmin=0,
        )

        colorbar = fig.colorbar(grid, ax=ax)
        colorbar.set_label("Precipitation (mm)")

        ax.set_title(f"PRISM daily precipitation — {requested_date}")
        ax.set_xlabel("Longitude")
        ax.set_ylabel("Latitude")

        fig.tight_layout()

        output_path = project_dir / f"prism_map_{requested_date}.png"
        fig.savefig(output_path, dpi=200)

        print("Map saved:", output_path)
        plt.show()