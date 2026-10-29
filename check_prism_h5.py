from pathlib import Path

import h5py
import numpy as np

project_dir = Path(__file__).resolve().parent
file_path = project_dir / "prism_dc.h5"

with h5py.File(file_path, "r") as h5:
    dates = h5["dates"].asstr()[:]
    rainfall = h5["precipitation_mm"]
    latitude = h5["latitude"][:]
    longitude = h5["longitude"][:]

    # Read the first day's grid
    first_day = rainfall[0]

    print("File opened successfully!")
    print("Number of dates:", len(dates))
    print("Rainfall data shape:", rainfall.shape)
    print("First date:", dates[0])
    print("Last date:", dates[-1])
    print("Latitude points:", len(latitude))
    print("Longitude points:", len(longitude))
    print("First day minimum rainfall:", np.nanmin(first_day), "mm")
    print("First day maximum rainfall:", np.nanmax(first_day), "mm")
    print("First day missing cells:", np.isnan(first_day).sum())