from datetime import datetime
from pathlib import Path

import h5py
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import BoundaryNorm, ListedColormap
from matplotlib.patches import Patch
from rasterio.warp import transform_geom

project_dir = Path(__file__).resolve().parent
if project_dir.name.lower() == "reports":
    project_dir = project_dir.parent

figures_dir = project_dir / "figures"
figures_dir.mkdir(exist_ok=True)

h5_file = project_dir / "prism_dc_events.h5"
output_file = figures_dir / "nasa_event_124_context.png"


def text(value):
    return value.decode() if isinstance(value, bytes) else str(value)


# Display categories; original values in HDF5 remain unchanged.
class_codes = [0, 1, 2, 252, 253, 254, 255]
labels = [
    "Not water",
    "Open water",
    "Partial water",
    "Snow/ice class",
    "Cloud/cloud shadow",
    "Ocean masked",
    "Missing data",
]
colors = [
    "#f0eadc",
    "#1764ab",
    "#79c9ef",
    "#80eee6",
    "#a6a6a6",
    "#603b83",
    "#f7c9d0",
]

cmap = ListedColormap(colors)
cmap.set_bad("white")
norm = BoundaryNorm(np.arange(-0.5, 7.5, 1), cmap.N)

with h5py.File(h5_file, "r") as h5:
    scenes = h5["nasa/scenes"]
    scene_ids = sorted(scenes)

    if not scene_ids:
        raise RuntimeError("No saved NASA scenes found.")

    boundary = h5["dc_boundary"]
    boundary_crs = text(boundary.attrs["crs"])
    rings = [
        np.asarray(boundary[name])
        for name in sorted(boundary)
        if name.startswith("ring_")
    ]

    fig, axes = plt.subplots(
        1,
        len(scene_ids),
        figsize=(13, 8),
        squeeze=False,
    )

    for ax, scene_id in zip(axes.flat, scene_ids):
        scene = scenes[scene_id]

        water = scene["water_class"][:]
        dc_mask = scene["dc_mask"][:]
        x = scene["x"][:]
        y = scene["y"][:]

        # GDAL transform: x origin, x step, rotation,
        # y origin, rotation, y step.
        transform = scene.attrs["transform_gdal"]
        dx = float(transform[1])
        dy = float(transform[5])

        display = np.full(water.shape, np.nan)

        for index, code in enumerate(class_codes):
            display[dc_mask & (water == code)] = index

        unknown = dc_mask & ~np.isin(water, class_codes)
        if unknown.any():
            raise RuntimeError("Unexpected water classification.")

        extent = [
            x[0] - dx / 2,
            x[-1] + dx / 2,
            y[-1] + dy / 2,
            y[0] - dy / 2,
        ]

        ax.imshow(
            np.ma.masked_invalid(display),
            cmap=cmap,
            norm=norm,
            extent=extent,
            origin="upper",
            interpolation="nearest",
        )

        projected_rings = []

        for ring in rings:
            polygon = transform_geom(
                boundary_crs,
                text(scene.attrs["crs"]),
                {
                    "type": "Polygon",
                    "coordinates": [ring.tolist()],
                },
            )

            for projected_ring in polygon["coordinates"]:
                coordinates = np.asarray(projected_ring)
                projected_rings.append(coordinates)
                ax.plot(
                    coordinates[:, 0],
                    coordinates[:, 1],
                    color="black",
                    linewidth=1,
                )

        points = np.concatenate(projected_rings)
        padding = 500

        ax.set_xlim(
            points[:, 0].min() - padding,
            points[:, 0].max() + padding,
        )
        ax.set_ylim(
            points[:, 1].min() - padding,
            points[:, 1].max() + padding,
        )
        ax.set_aspect("equal")

        acquisition = datetime.fromisoformat(
            text(scene.attrs["acquisition_start_utc"])
            .replace("Z", "+00:00")
        )
        hours_before = -float(
            scene.attrs["hours_from_event_start"]
        )
        usable_pct = float(scene.attrs["usable_dc_pct"])

        sensor = (
            "Landsat 8" if "_L8_" in scene_id
            else "Sentinel-2C"
        )

        ax.set_title(
            f"{sensor} | {acquisition:%Y-%m-%d %H:%M} UTC\n"
            f"{hours_before:.2f} hours before event start\n"
            f"Usable DC coverage: {usable_pct:.2f}%",
            fontsize=10,
        )
        ax.set_xlabel("Easting (m), WGS 84 / UTM zone 18N")
        ax.set_ylabel("Northing (m)")
        ax.ticklabel_format(style="plain", useOffset=False)
        ax.tick_params(axis="x", labelrotation=25, labelsize=8)
        ax.tick_params(axis="y", labelsize=8)

    fig.suptitle(
        "NASA OPERA DSWx-HLS: surface-water context before event 124\n"
        "Flood event: 13 July 2025, 18:00–19:05 UTC",
        fontsize=13,
        y=0.98,
    )

    legend_items = [
        Patch(facecolor=color, label=label)
        for color, label in zip(colors, labels)
    ]

    fig.legend(
        handles=legend_items,
        loc="lower center",
        bbox_to_anchor=(0.5, 0.07),
        ncol=4,
        frameon=False,
        fontsize=9,
    )

    fig.text(
        0.5,
        0.025,
        "Both scenes precede the flood. Clouds obscure much of DC.\n"
        "Water classes include permanent water; these maps do not "
        "establish flood extent. Native 30 m pixels.",
        ha="center",
        fontsize=9,
    )

    fig.subplots_adjust(
        left=0.08,
        right=0.98,
        top=0.80,
        bottom=0.24,
        wspace=0.30,
    )

    fig.savefig(output_file, dpi=200, facecolor="white")

print(f"Saved: {output_file}")
print("Maps read from the integrated HDF5 file.")
plt.show()