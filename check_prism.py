from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile

import rasterio
from rasterio.windows import from_bounds

project_dir = Path(__file__).parent
zip_path = project_dir / "prism_ppt_us_30s_19960120.zip"

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

    with rasterio.open(tif_path) as dataset:
        print("Coordinate system:", dataset.crs)
        print("Native resolution:", dataset.res)
        print("Missing-value marker:", dataset.nodata)

        # A bounding box that includes DC and its surroundings.
        dc_bounds = (-77.15, 38.78, -76.90, 39.00)

        if not dataset.crs or dataset.crs.to_epsg() != 4269:
            raise ValueError(
                "Unexpected coordinate system; check before using DC bounds."
            )

        window = from_bounds(*dc_bounds, transform=dataset.transform)
        window = window.round_offsets().round_lengths()
        data = dataset.read(1, window=window, masked=True)

        print("DC-area grid shape:", data.shape)
        print("Valid grid cells:", data.count())

        if data.count() > 0:
            print("Minimum value:", float(data.min()))
            print("Maximum value:", float(data.max()))