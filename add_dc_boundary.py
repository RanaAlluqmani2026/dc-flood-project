import json
from pathlib import Path

import h5py
import numpy as np

project_dir = Path(__file__).resolve().parent

boundary_file = project_dir / "dc_boundary.json"
h5_file = project_dir / "prism_dc_events.h5"

boundary = json.loads(
    boundary_file.read_text(encoding="utf-8")
)

# Verify the coordinates use the PRISM coordinate system.
spatial_reference = boundary.get("spatialReference", {})
crs_code = spatial_reference.get(
    "latestWkid",
    spatial_reference.get("wkid"),
)

if crs_code != 4269:
    raise ValueError(
        f"Expected boundary CRS EPSG:4269, got {crs_code}"
    )

rings = []

for feature in boundary["features"]:
    for ring in feature["geometry"]["rings"]:
        coordinates = np.asarray(ring, dtype="float64")

        if (
            coordinates.ndim != 2
            or coordinates.shape[1] != 2
            or len(coordinates) < 4
            or not np.isfinite(coordinates).all()
        ):
            raise ValueError("Invalid boundary coordinates.")

        rings.append(coordinates)

if not rings:
    raise ValueError("No boundary rings were found.")

with h5py.File(h5_file, "r+") as h5:
    if h5.attrs.get("crs") != "EPSG:4269":
        raise ValueError("PRISM and boundary CRS do not match.")

    if "dc_boundary" in h5:
        raise ValueError(
            "DC boundary is already stored. Do not run again."
        )

    group = h5.create_group("dc_boundary")

    group.attrs["source"] = boundary["source"]
    group.attrs["retrieval_url"] = boundary["retrieval_url"]
    group.attrs["crs"] = "EPSG:4269"
    group.attrs["coordinate_order"] = "longitude, latitude"
    group.attrs["units"] = "degrees"
    group.attrs["purpose"] = "Geographic context for PRISM maps"

    for index, coordinates in enumerate(rings):
        group.create_dataset(
            f"ring_{index:03d}",
            data=coordinates,
            compression="gzip",
        )

print("Finished! DC boundary added to:", h5_file.name)
print("Boundary rings stored:", len(rings))