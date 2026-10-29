from datetime import datetime, timedelta
from pathlib import Path

import h5py
import numpy as np

project_dir = Path(__file__).resolve().parent
database = project_dir / "prism_dc_events.h5"

with h5py.File(database, "r+") as h5:
    rainfall = h5["precipitation_mm"]
    dates = list(h5["dates"].asstr()[:])

    rainfall.attrs["source"] = (
        "PRISM Climate Group, Oregon State University"
    )
    rainfall.attrs["source_variable"] = "ppt"
    rainfall.attrs["units"] = "mm"
    rainfall.attrs["description"] = (
        "Daily total precipitation, including rain and melted snow"
    )
    rainfall.attrs["spatial_support"] = "Raster grid cells"
    rainfall.attrs["dimensions"] = "date, latitude, longitude"
    rainfall.attrs["crs"] = h5.attrs["crs"]
    rainfall.attrs["native_grid_spacing"] = "30 arc-seconds"
    rainfall.attrs["product_resolution_label"] = "800 m"
    rainfall.attrs["temporal_resolution"] = "24 hours"
    rainfall.attrs["stored_missing_value"] = "NaN"
    rainfall.attrs["processing"] = (
        "Downloaded daily PRISM ZIP files; extracted GeoTIFFs; "
        "cropped a rectangular area covering DC and surroundings; "
        "converted masked NoData cells to NaN; stored float32 "
        "arrays with gzip compression and one-day chunks. "
        "No reprojection, resampling, or unit conversion applied "
        "to the precipitation grids."
    )
    rainfall.attrs["limitations"] = (
        "Daily estimates cannot isolate rainfall during flood hours. "
        "The rectangle includes locations outside DC. "
        "Grid spacing does not imply measurement accuracy."
    )
    rainfall.attrs["download_url_pattern"] = (
        "https://services.nacse.org/prism/data/get/us/800m/ppt/YYYYMMDD"
    )
    rainfall.attrs["documentation_url"] = (
        "https://prism.oregonstate.edu/documents/PRISM_datasets.pdf"
    )

    h5["latitude"].attrs["units"] = "degrees_north"
    h5["longitude"].attrs["units"] = "degrees_east"
    h5["latitude"].attrs["crs"] = h5.attrs["crs"]
    h5["longitude"].attrs["crs"] = h5.attrs["crs"]

    h5["dates"].attrs["meaning"] = (
        "Date on which the 24-hour PRISM interval ends at 12:00 UTC"
    )
    h5["dates"].attrs["coverage"] = (
        "Selected event-related dates only; not a continuous daily series"
    )

    # Store explicit UTC interval boundaries for each date.
    starts = []
    ends = []

    for date in dates:
        end = datetime.strptime(date, "%Y-%m-%d").replace(hour=12)
        start = end - timedelta(days=1)

        starts.append(start.strftime("%Y-%m-%dT%H:%M:%SZ"))
        ends.append(end.strftime("%Y-%m-%dT%H:%M:%SZ"))

    string_type = h5py.string_dtype(encoding="utf-8")

    for name, values in [
        ("prism_interval_start_utc", starts),
        ("prism_interval_end_utc", ends),
    ]:
        if name in h5:
            if list(h5[name].asstr()[:]) != values:
                raise ValueError(f"Existing {name} does not match.")
        else:
            h5.create_dataset(
                name,
                data=np.array(values, dtype=object),
                dtype=string_type,
            )

        h5[name].attrs["time_zone"] = "UTC"
        h5[name].attrs["dimensions"] = "date"

print("PRISM metadata saved successfully.")
print("Daily interval boundaries stored in UTC.")
print("First interval:", starts[0], "to", ends[0])
print("Precipitation values were not changed.")