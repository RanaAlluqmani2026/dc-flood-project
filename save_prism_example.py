from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile

import h5py
import rasterio
from rasterio.windows import from_bounds

project_dir = Path(__file__).parent
zip_path = project_dir / "prism_ppt_us_30s_19960120.zip"
output_path = project_dir / "prism_example.h5"

# Rectangle covering Washington, DC and nearby areas.
dc_bounds = (-77.15, 38.78, -76.90, 39.00)

with TemporaryDirectory() as temp_dir:
    with ZipFile(zip_path) as archive:
        tif_files = [
            name for name in archive.namelist()
            if name.lower().endswith(".tif")
        ]

        if len(tif_files) != 1:
            raise ValueError(f"Expected one TIF file, found: {tif_files}")

        archive.extract(tif_files[0], temp_dir)
        tif_path = Path(temp_dir) / tif_files[0]

    with rasterio.open(tif_path) as source:
        if not source.crs or source.crs.to_epsg() != 4269:
            raise ValueError(f"Unexpected coordinate system: {source.crs}")

        window = from_bounds(*dc_bounds, transform=source.transform)
        window = window.round_offsets().round_lengths()
        precipitation = source.read(1, window=window)
        transform = source.window_transform(window)

        # Coordinates of the centers of grid cells.
        longitude = [
            transform.c + (col + 0.5) * transform.a
            for col in range(precipitation.shape[1])
        ]
        latitude = [
            transform.f + (row + 0.5) * transform.e
            for row in range(precipitation.shape[0])
        ]

        crs = source.crs.to_string()
        nodata = source.nodata
        resolution = source.res

# Create a new example file; do not overwrite an existing one.
with h5py.File(output_path, "x") as database:
    group = database.create_group("gridded/prism/1996-01-20")

    values = group.create_dataset(
        "precipitation",
        data=precipitation,
        compression="gzip",
    )
    group.create_dataset("longitude", data=longitude)
    group.create_dataset("latitude", data=latitude)

    values.attrs["source"] = "PRISM"
    values.attrs["variable"] = "daily precipitation"
    values.attrs["date_label"] = "1996-01-20"
    values.attrs["crs"] = crs
    values.attrs["nodata"] = nodata
    values.attrs["resolution_degrees"] = resolution
    values.attrs["source_file"] = zip_path.name

print(f"Created: {output_path.name}")
print(f"Stored grid shape: {precipitation.shape}")