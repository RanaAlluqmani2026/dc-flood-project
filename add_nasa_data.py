import csv
import json
import math
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
coverage_file = reports_dir / "nasa_coverage_event_124.csv"
download_log = reports_dir / "nasa_download_log.csv"

with catalog_file.open(encoding="utf-8") as file:
    catalog = json.load(file)

entries = catalog["catalog_response"]["feed"]["entry"]

# One scene with the best usable DC coverage, and one
# closer to the event. Both observations precede the event.
selected = [
    entry for entry in entries
    if (
        "_T18SUJ_20250711T154550Z_" in entry["title"]
        or "_T18SUJ_20250713T155001Z_" in entry["title"]
    )
]

if len(selected) != 2:
    raise RuntimeError("Expected exactly two selected scenes.")

with coverage_file.open(newline="", encoding="utf-8-sig") as file:
    coverage = {
        row["scene_id"]: row
        for row in csv.DictReader(file)
    }

with download_log.open(newline="", encoding="utf-8-sig") as file:
    download_records = list(csv.DictReader(file))

string_type = h5py.string_dtype(encoding="utf-8")

with h5py.File(h5_file, "r+") as h5:
    if "nasa" in h5:
        raise RuntimeError(
            "NASA data already exist. Nothing was changed."
        )

    if "_nasa_building" in h5:
        raise RuntimeError(
            "An unfinished NASA group exists. Stop and review it."
        )

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

    staging = h5.create_group("_nasa_building")

    try:
        staging.attrs["source"] = "NASA/JPL/PO.DAAC"
        staging.attrs["product"] = "OPERA_L3_DSWX-HLS_V1"
        staging.attrs["event_id"] = 124
        staging.attrs["purpose"] = (
            "Contextual surface-water observations before event 124."
        )
        staging.attrs["limitations"] = (
            "Both selected scenes precede the flood. "
            "Clouds obscure much of DC. Water classifications "
            "include permanent water and do not prove flooding. "
            "Scenes are stored independently, not mosaicked."
        )
        staging.attrs["search_url"] = catalog["search_url"]
        staging.attrs["catalog_retrieved_utc"] = (
            catalog["retrieved_utc"]
        )
        staging.attrs["documentation_url"] = (
            "https://podaac.jpl.nasa.gov/dataset/"
            "OPERA_L3_DSWX-HLS_V1"
        )

        staging.create_dataset(
            "catalog_json",
            data=json.dumps(catalog),
            dtype=string_type,
        )
        staging.create_dataset(
            "coverage_csv",
            data=coverage_file.read_text(encoding="utf-8-sig"),
            dtype=string_type,
        )

        scenes = staging.create_group("scenes")

        for entry in selected:
            scene_id = entry["title"]
            water_file = download_dir / f"{scene_id}_B01_WTR.tif"
            cloud_file = download_dir / f"{scene_id}_B09_CLOUD.tif"

            with rasterio.open(water_file) as water:
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

                inverse = ~water.transform
                corners = [
                    inverse * (x, y)
                    for x in (
                        points[:, 0].min(), points[:, 0].max()
                    )
                    for y in (
                        points[:, 1].min(), points[:, 1].max()
                    )
                ]

                c0 = math.floor(min(p[0] for p in corners))
                c1 = math.ceil(max(p[0] for p in corners))
                r0 = math.floor(min(p[1] for p in corners))
                r1 = math.ceil(max(p[1] for p in corners))

                window = Window(
                    c0, r0, c1 - c0, r1 - r0
                ).intersection(
                    Window(0, 0, water.width, water.height)
                )

                values = water.read(1, window=window)
                transform = water.window_transform(window)

                if not (
                    transform.b == 0 and transform.d == 0
                ):
                    raise RuntimeError("Rotated grid needs review.")

                dc_mask = np.zeros(values.shape, dtype=bool)

                for polygon in polygons:
                    dc_mask ^= geometry_mask(
                        [polygon],
                        out_shape=values.shape,
                        transform=transform,
                        invert=True,
                        all_touched=False,
                    )

                with rasterio.open(cloud_file) as cloud:
                    if (
                        cloud.crs != water.crs
                        or cloud.transform != water.transform
                        or cloud.shape != water.shape
                    ):
                        raise RuntimeError("Layer grids differ.")

                    cloud_values = cloud.read(1, window=window)
                    cloud_tags = cloud.tags()
                    cloud_nodata = cloud.nodata

                group = scenes.create_group(scene_id)

                group.attrs["event_id"] = 124
                group.attrs["acquisition_start_utc"] = (
                    entry["time_start"]
                )
                group.attrs["acquisition_end_utc"] = (
                    entry.get("time_end", entry["time_start"])
                )
                group.attrs["crs"] = str(water.crs)
                group.attrs["crs_wkt"] = water.crs.to_wkt()
                group.attrs["transform_gdal"] = (
                    transform.to_gdal()
                )
                group.attrs["coordinate_units"] = "metres"
                group.attrs["processing"] = (
                    "Native-grid rectangular crop around DC; "
                    "no resampling or reprojection of raster values. "
                    "Boundary transformed to raster CRS. "
                    "DC mask uses pixel centers."
                )
                group.attrs["source_raster_tags_json"] = (
                    json.dumps(water.tags())
                )

                for key in (
                    "usable_dc_pct",
                    "cloud_shadow_dc_pct",
                    "missing_or_outside_tile_dc_pct",
                    "hours_from_event_start",
                ):
                    group.attrs[key] = float(
                        coverage[scene_id][key]
                    )

                group.attrs["acquisition_relation"] = (
                    coverage[scene_id]["acquisition_relation"]
                )

                height, width = values.shape
                x = transform.c + (
                    np.arange(width) + 0.5
                ) * transform.a
                y = transform.f + (
                    np.arange(height) + 0.5
                ) * transform.e

                group.create_dataset("x", data=x)
                group.create_dataset("y", data=y)

                group["x"].attrs["units"] = "metres"
                group["y"].attrs["units"] = "metres"

                group.create_dataset(
                    "dc_mask",
                    data=dc_mask,
                    compression="gzip",
                )

                usable = dc_mask & np.isin(values, [0, 1, 2])
                group.create_dataset(
                    "usable_dc_mask",
                    data=usable,
                    compression="gzip",
                )

                layer_details = [
                    (
                        "water_class",
                        values,
                        "_B01_WTR.tif",
                        water.nodata,
                    ),
                    (
                        "cloud_quality",
                        cloud_values,
                        "_B09_CLOUD.tif",
                        cloud_nodata,
                    ),
                ]

                for name, array, suffix, nodata in layer_details:
                    dataset = group.create_dataset(
                        name,
                        data=array,
                        compression="gzip",
                        shuffle=True,
                    )
                    dataset.attrs["dimensions"] = "y, x"
                    dataset.attrs["units"] = "classification code"
                    dataset.attrs["source_filename"] = (
                        scene_id + suffix
                    )

                    if nodata is not None:
                        dataset.attrs["source_nodata"] = nodata

                    source_urls = [
                        link["href"]
                        for link in entry.get("links", [])
                        if link.get("href", "").startswith("https://")
                        and link["href"].endswith(suffix)
                    ]

                    if len(source_urls) != 1:
                        raise RuntimeError("Source URL is ambiguous.")

                    dataset.attrs["source_url"] = source_urls[0]

                    records = [
                        record
                        for record in download_records
                        if record["filename"] == scene_id + suffix
                    ]
                    dataset.attrs["download_log_json"] = (
                        json.dumps(records)
                    )

                group["water_class"].attrs["class_legend"] = (
                    "0=not water; 1=open water; 2=partial water; "
                    "252=snow/ice; 253=cloud/cloud shadow; "
                    "254=ocean masked; 255=missing"
                )
                group["cloud_quality"].attrs["interpretation"] = (
                    "Original B09 quality codes preserved; "
                    "not a binary cloud mask."
                )
                group["cloud_quality"].attrs["source_tags_json"] = (
                    json.dumps(cloud_tags)
                )

                print(
                    f"Prepared: {scene_id}\n"
                    f"  Grid: {values.shape}; "
                    f"usable DC pixels in crop: {usable.sum()}"
                )

        h5.flush()
        h5.move("_nasa_building", "nasa")
        h5.flush()

    except Exception:
        if "_nasa_building" in h5:
            del h5["_nasa_building"]
        raise

print("\nNASA scenes added: 2")
print("Saved inside: prism_dc_events.h5")
print("PRISM and station groups preserved.")
print("Next: visualize the saved NASA scenes.")