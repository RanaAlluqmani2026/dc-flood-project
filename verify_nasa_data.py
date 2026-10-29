from pathlib import Path

import h5py
import numpy as np
import rasterio
from rasterio.windows import Window
from rasterio.transform import Affine

project_dir = Path(__file__).resolve().parent
if project_dir.name.lower() == "reports":
    project_dir = project_dir.parent

h5_file = project_dir / "prism_dc_events.h5"
download_dir = project_dir / "nasa_downloads"
report_file = project_dir / "reports" / "nasa_verification.txt"

lines = []


def record(message):
    print(message)
    lines.append(message)


def check(condition, message):
    if not condition:
        raise RuntimeError(message)


with h5py.File(h5_file, "r") as h5:
    check("stations" in h5, "Station group is missing.")
    check(
        "precipitation_mm" in h5,
        "PRISM precipitation dataset is missing.",
    )
    check("nasa/scenes" in h5, "NASA scenes are missing.")

    scenes = h5["nasa/scenes"]
    check(len(scenes) == 2, "Expected two NASA scenes.")

    record("NASA scenes: 2")
    record("PRISM precipitation and station groups: present")

    for scene_id in sorted(scenes):
        scene = scenes[scene_id]
        saved_transform = Affine.from_gdal(
            *scene.attrs["transform_gdal"]
        )

        water = scene["water_class"][:]
        dc_mask = scene["dc_mask"][:]
        usable_mask = scene["usable_dc_mask"][:]

        check(
            np.array_equal(
                usable_mask,
                dc_mask & np.isin(water, [0, 1, 2]),
            ),
            "Usable-pixel mask is inconsistent.",
        )

        for name in ("water_class", "cloud_quality"):
            saved = scene[name][:]
            filename = scene[name].attrs["source_filename"]

            if isinstance(filename, bytes):
                filename = filename.decode()

            with rasterio.open(download_dir / filename) as source:
                col_offset, row_offset = (
                    ~source.transform
                ) * (
                    saved_transform.c,
                    saved_transform.f,
                )

                check(
                    np.isclose(col_offset, round(col_offset))
                    and np.isclose(row_offset, round(row_offset)),
                    "Saved raster is not aligned to the source grid.",
                )

                window = Window(
                    round(col_offset),
                    round(row_offset),
                    saved.shape[1],
                    saved.shape[0],
                )

                original = source.read(1, window=window)

                check(
                    np.array_equal(saved, original),
                    f"Source values differ: {scene_id}/{name}",
                )
                check(
                    source.window_transform(window).almost_equals(
                        saved_transform
                    ),
                    "Saved transform differs from source window.",
                )
                check(
                    source.crs == rasterio.crs.CRS.from_user_input(
                        scene.attrs["crs"]
                    ),
                    "Saved CRS differs from the source.",
                )

        x_expected = saved_transform.c + (
            np.arange(water.shape[1]) + 0.5
        ) * saved_transform.a

        y_expected = saved_transform.f + (
            np.arange(water.shape[0]) + 0.5
        ) * saved_transform.e

        check(
            np.allclose(scene["x"][:], x_expected)
            and np.allclose(scene["y"][:], y_expected),
            "Coordinate arrays are inconsistent.",
        )

        record(f"\nScene: {scene_id}")
        record("Water and cloud values match original raster windows.")
        record("Native grid, CRS, coordinates and usable mask: PASS")
        record(f"Saved shape: {water.shape}")
        record(f"Usable DC pixels: {int(usable_mask.sum())}")

record("\nNASA verification: PASS")
record("This check does not establish that flooding was observed.")

report_file.write_text(
    "\n".join(lines) + "\n",
    encoding="utf-8",
)

print(f"\nSaved: {report_file.name}")