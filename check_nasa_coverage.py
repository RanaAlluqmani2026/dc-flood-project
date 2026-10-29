import csv
import json
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path

import h5py
import numpy as np
import rasterio
from rasterio.features import geometry_mask
from rasterio.warp import transform_geom
from rasterio.windows import Window

project_dir = Path(__file__).resolve().parent
if project_dir.name.lower() == "reports":
    project_dir = project_dir.parent

reports_dir = project_dir / "reports"
download_dir = project_dir / "nasa_downloads"

h5_file = project_dir / "prism_dc_events.h5"
catalog_file = reports_dir / "nasa_search_event_124.json"
output_file = reports_dir / "nasa_coverage_event_124.csv"

# Read the event from the original event index.
with (project_dir / "DC_flood_times.csv").open(
    newline="", encoding="utf-8-sig"
) as file:
    events = list(csv.DictReader(file))

event = events[123]
fixed_est = timezone(timedelta(hours=-5))

event_start = datetime.strptime(
    f"{event['begin_date']} {event['begin_time']}",
    "%Y-%m-%d %H:%M",
).replace(tzinfo=fixed_est).astimezone(timezone.utc)

event_end = datetime.strptime(
    f"{event['end_date']} {event['end_time']}",
    "%Y-%m-%d %H:%M",
).replace(tzinfo=fixed_est).astimezone(timezone.utc)

with catalog_file.open(encoding="utf-8") as file:
    catalog = json.load(file)

entries = catalog["catalog_response"]["feed"]["entry"]
scene_times = {
    entry["title"]: entry["time_start"]
    for entry in entries
}

# Read the previously saved DC boundary.
with h5py.File(h5_file, "r") as h5:
    boundary = h5["dc_boundary"]
    boundary_crs = boundary.attrs["crs"]

    if isinstance(boundary_crs, bytes):
        boundary_crs = boundary_crs.decode()

    rings = [
        np.asarray(boundary[name])
        for name in sorted(boundary)
        if name.startswith("ring_")
    ]

if not rings:
    raise RuntimeError("No DC boundary rings found.")

water_files = sorted(download_dir.glob("*_B01_WTR.tif"))

if not water_files:
    raise RuntimeError("No NASA water rasters found.")

rows = []

for water_file in water_files:
    scene_id = water_file.name.removesuffix("_B01_WTR.tif")
    cloud_file = download_dir / f"{scene_id}_B09_CLOUD.tif"

    if not cloud_file.exists():
        raise FileNotFoundError(cloud_file)

    with rasterio.open(water_file) as water:
        # Transform the boundary to the raster's native CRS.
        polygons = [
            transform_geom(
                str(boundary_crs),
                water.crs,
                {
                    "type": "Polygon",
                    "coordinates": [ring.tolist()],
                },
            )
            for ring in rings
        ]

        points = np.concatenate([
            np.asarray(polygon["coordinates"][0])
            for polygon in polygons
        ])

        # Build a window covering ALL of DC, including areas
        # outside this tile. Outside-tile pixels become missing.
        inverse = ~water.transform
        pixel_corners = [
            inverse * (x, y)
            for x in (points[:, 0].min(), points[:, 0].max())
            for y in (points[:, 1].min(), points[:, 1].max())
        ]

        col_start = math.floor(min(p[0] for p in pixel_corners))
        col_end = math.ceil(max(p[0] for p in pixel_corners))
        row_start = math.floor(min(p[1] for p in pixel_corners))
        row_end = math.ceil(max(p[1] for p in pixel_corners))

        window = Window(
            col_start,
            row_start,
            col_end - col_start,
            row_end - row_start,
        )

        values = water.read(
            1,
            window=window,
            boundless=True,
            fill_value=255,
        )
        window_transform = water.window_transform(window)

        # Odd-even ring rule preserves holes in the DC boundary.
        inside_dc = np.zeros(values.shape, dtype=bool)

        for polygon in polygons:
            inside_dc ^= geometry_mask(
                [polygon],
                out_shape=values.shape,
                transform=window_transform,
                invert=True,
                all_touched=False,
            )

        dc_values = values[inside_dc]

        with rasterio.open(cloud_file) as cloud:
            if (
                cloud.crs != water.crs
                or cloud.transform != water.transform
                or cloud.shape != water.shape
            ):
                raise RuntimeError(
                    f"Water/cloud grids do not match: {scene_id}"
                )

            cloud_values = cloud.read(
                1,
                window=window,
                boundless=True,
                fill_value=255,
            )[inside_dc]

        crs = str(water.crs)
        resolution = water.res

    total = dc_values.size

    if total == 0:
        raise RuntimeError("DC boundary contains no pixel centers.")

    # Official B01_WTR classification codes.
    usable = np.isin(dc_values, [0, 1, 2])
    cloudy = dc_values == 253
    missing = dc_values == 255
    snow = dc_values == 252
    ocean = dc_values == 254
    known = np.isin(dc_values, [0, 1, 2, 252, 253, 254, 255])

    if not known.all():
        raise RuntimeError(f"Unexpected water classes: {scene_id}")

    acquisition = datetime.fromisoformat(
        scene_times[scene_id].replace("Z", "+00:00")
    )

    if acquisition < event_start:
        relation = "before_event"
    elif acquisition > event_end:
        relation = "after_event"
    else:
        relation = "during_event"

    codes, counts = np.unique(cloud_values, return_counts=True)
    cloud_histogram = {
        str(int(code)): int(count)
        for code, count in zip(codes, counts)
    }

    rows.append({
        "event_id": 124,
        "scene_id": scene_id,
        "acquisition_start_utc": acquisition.isoformat(),
        "event_start_utc": event_start.isoformat(),
        "event_end_utc": event_end.isoformat(),
        "acquisition_relation": relation,
        "hours_from_event_start": round(
            (acquisition - event_start).total_seconds() / 3600, 3
        ),
        "crs": crs,
        "pixel_width_native": resolution[0],
        "pixel_height_native": resolution[1],
        "dc_pixel_centers": total,
        "usable_dc_pct": round(100 * usable.sum() / total, 2),
        "cloud_shadow_dc_pct": round(100 * cloudy.sum() / total, 2),
        "missing_or_outside_tile_dc_pct": round(
            100 * missing.sum() / total, 2
        ),
        "snow_ice_dc_pct": round(100 * snow.sum() / total, 2),
        "ocean_masked_dc_pct": round(100 * ocean.sum() / total, 2),
        "open_water_pixels": int((dc_values == 1).sum()),
        "partial_water_pixels": int((dc_values == 2).sum()),
        "cloud_layer_code_counts": json.dumps(cloud_histogram),
    })

rows.sort(key=lambda row: row["usable_dc_pct"], reverse=True)

with output_file.open("w", newline="", encoding="utf-8") as file:
    writer = csv.DictWriter(file, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)

print(f"Scenes checked: {len(rows)}")
print(f"Event 124 UTC: {event_start} to {event_end}")
print()

for row in rows:
    print(row["scene_id"])
    print(
        f"  Usable DC: {row['usable_dc_pct']}% | "
        f"Cloud/shadow: {row['cloud_shadow_dc_pct']}% | "
        f"Missing/outside tile: "
        f"{row['missing_or_outside_tile_dc_pct']}%"
    )
    print(f"  Acquisition: {row['acquisition_relation']}")

print(f"\nSaved: {output_file.name}")
print("Percentages use all DC pixel centers on each native grid.")
print("Surface water classifications are not proof of flooding.")