import csv
import tempfile
import zipfile
from pathlib import Path

import h5py
import numpy as np
import rasterio
from rasterio.windows import from_bounds, transform as window_transform


# Files and folders inside the project
project_dir = Path(__file__).resolve().parent
dates_file = project_dir / "prism_event_dates.csv"
download_dir = project_dir / "prism_downloads"

# Use a temporary output file until processing succeeds
output_file = project_dir / "prism_dc.h5"
temporary_output = project_dir / "prism_dc_building.h5"

# Bounding box: DC and surrounding area
# Order: west, south, east, north
bounds = (-77.15, 38.78, -76.90, 39.00)


# Read the unique PRISM dates needed for the flood events
with dates_file.open(newline="", encoding="utf-8-sig") as file:
    reader = csv.DictReader(file)
    dates = sorted({row["prism_date"].strip() for row in reader})

if not dates:
    raise ValueError("No PRISM dates were found in prism_event_dates.csv.")

if output_file.exists():
    raise FileExistsError(
        f"{output_file.name} already exists. Rename it before running again."
    )

if temporary_output.exists():
    raise FileExistsError(
        f"{temporary_output.name} already exists. "
        "Remove or rename it before running again."
    )


try:
    with h5py.File(temporary_output, "w") as h5:
        h5.attrs["description"] = "Daily PRISM precipitation for DC and surrounding area"
        h5.attrs["units"] = "mm"
        h5.attrs["source"] = "PRISM Climate Group, Oregon State University"
        h5.attrs["prism_day"] = (
            "24 hours ending at 12:00 UTC on the date shown"
        )
        h5.attrs["bounding_box_west_south_east_north"] = bounds

        string_type = h5py.string_dtype(encoding="utf-8")
        h5.create_dataset("dates", data=np.array(dates, dtype=object), dtype=string_type)

        precipitation = None
        reference_transform = None
        reference_crs = None
        reference_shape = None

        for index, date in enumerate(dates):
            date_code = date.replace("-", "")
            zip_path = download_dir / f"prism_ppt_us_30s_{date_code}.zip"

            if not zip_path.exists():
                raise FileNotFoundError(f"Missing ZIP file: {zip_path.name}")

            # Extract the TIF to a temporary folder for reading.
            with tempfile.TemporaryDirectory() as temp_dir:
                with zipfile.ZipFile(zip_path) as archive:
                    tif_files = [
                        name for name in archive.namelist()
                        if name.lower().endswith(".tif")
                    ]

                    if len(tif_files) != 1:
                        raise ValueError(
                            f"{zip_path.name}: expected one TIF, "
                            f"found {len(tif_files)}"
                        )

                    tif_path = Path(temp_dir) / "daily_prism.tif"
                    with archive.open(tif_files[0]) as source, tif_path.open("wb") as target:
                        while True:
                            chunk = source.read(1024 * 1024)
                            if not chunk:
                                break
                            target.write(chunk)

                with rasterio.open(tif_path) as raster:
                    if raster.crs is None or raster.crs.to_epsg() != 4269:
                        raise ValueError(
                            f"{zip_path.name}: unexpected CRS {raster.crs}"
                        )

                    window = from_bounds(*bounds, transform=raster.transform)
                    window = window.round_offsets().round_lengths()
                    current_transform = window_transform(window, raster.transform)

                    data = raster.read(1, window=window, masked=True)
                    data = np.ma.filled(data.astype("float32"), np.nan)

                    if not np.isfinite(data).any():
                        raise ValueError(
                            f"{zip_path.name}: no valid values in the selected area"
                        )

                    if precipitation is None:
                        reference_transform = current_transform
                        reference_crs = raster.crs
                        reference_shape = data.shape

                        rows, columns = data.shape
                        x = current_transform.c + (
                            np.arange(columns) + 0.5
                        ) * current_transform.a
                        y = current_transform.f + (
                            np.arange(rows) + 0.5
                        ) * current_transform.e

                        h5.create_dataset("longitude", data=x)
                        h5.create_dataset("latitude", data=y)

                        precipitation = h5.create_dataset(
                            "precipitation_mm",
                            shape=(len(dates), rows, columns),
                            dtype="float32",
                            chunks=(1, rows, columns),
                            compression="gzip",
                            fillvalue=np.nan,
                        )

                        precipitation.attrs["dimensions"] = "date, latitude, longitude"
                        precipitation.attrs["units"] = "mm"
                        h5.attrs["crs"] = str(reference_crs)
                        h5.attrs["transform"] = tuple(reference_transform)

                    elif (
                        data.shape != reference_shape
                        or raster.crs != reference_crs
                        or not current_transform.almost_equals(reference_transform)
                    ):
                        raise ValueError(
                            f"{zip_path.name}: grid does not match the first file"
                        )

                    precipitation[index] = data

            print(f"{index + 1}/{len(dates)}: saved {date}", flush=True)

    temporary_output.replace(output_file)

except Exception:
    if temporary_output.exists():
        temporary_output.unlink()
    raise

print()
print(f"Finished! Created: {output_file.name}")
print(f"Number of PRISM dates: {len(dates)}")
print(f"Grid size: {reference_shape[0]} rows x {reference_shape[1]} columns")