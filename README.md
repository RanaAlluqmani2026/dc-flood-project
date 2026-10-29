# Environmental Database for Washington, DC Flood Events

STAT 6289 — Computing Environments  

- **Factor A:** PRISM gridded precipitation.
- **Factor B:** precipitation observations from stations physically inside Washington, DC.
- **Optional extension:** NASA OPERA DSWx-HLS surface-water observations.

## Purpose and implemented scope

This project organizes environmental observations around the instructor-provided DC flood-event records. It emphasizes data acquisition, metadata, reproducible processing, event-based retrieval, coverage assessment, and visualization. It is not a flood-prediction model.

The integrated database is **`prism_dc_events.h5`**. It contains PRISM grids, the event index and event-to-PRISM links, a DC boundary, two precipitation-station time series, and two NASA satellite scenes. Coverage and validation reports accompany the database.

The implemented outputs have been demonstrated locally. This README describes those outputs and their limitations; it does not claim complete station coverage, exact station–PRISM temporal equivalence, or satellite detection of the recorded flood. The supplied database and read/plot functions were additionally checked during packaging. A complete rebuild with fresh downloads and final confirmation against the original assignment rubric remain separate checks.

## Input events and time convention

`DC_flood_times.csv` is preserved without modification. It contains **125 records**. Each `event_id` is the original one-based row position; these are project-generated identifiers, not official event IDs. Preserve row order when reproducing the database.

Following the instructor's clarification, event times use **fixed EST (UTC−05:00) throughout the year**. No daylight-saving adjustment is applied. Converting an event to UTC therefore adds five hours, including in summer.

## Factor A: PRISM gridded precipitation

### Source and native resolution

Source: PRISM Climate Group, Oregon State University. Variable: `ppt`, daily precipitation including rain and melted snow, in millimeters.

Daily archives were obtained using:

```text
https://services.nacse.org/prism/data/get/us/800m/ppt/YYYYMMDD
```

The product is labeled 800 m, with native grid spacing of 30 arc-seconds (approximately 0.008333 degrees). Geographic cell dimensions vary with latitude. Full national ZIP archives were downloaded and cropped locally.

### Spatial processing

The requested longitude/latitude bounding box is:

| West | South | East | North |
| ---: | ---: | ---: | ---: |
| -77.15 | 38.78 | -76.90 | 39.00 |

This rectangle covers DC and nearby locations for geographic context. It is not a DC-only mask. The requested bounds were converted to a rounded native raster window; stored pixel edges can differ slightly from the requested bounds.

Each stored daily grid has **26 rows × 30 columns**. Grids retain **EPSG:4269 (NAD83)**, native cell spacing and precipitation units. No raster reprojection or resampling was applied. Masked source NoData cells were converted to `NaN`; arrays use float32, gzip compression and daily chunks.

Daily means in `reports/prism_daily_coverage.csv` describe valid cells in the stored rectangle, not a mean restricted to DC.

### Daily intervals and event mapping

A PRISM date labels the end of a 24-hour accumulation period at **12:00 UTC**, or **07:00 fixed EST**. For example, date `1996-01-20` represents 1996-01-19 12:00 UTC through 1996-01-20 12:00 UTC.

Positive-duration events and daily intervals use the half-open convention `[start, end)`. An event starting exactly at 07:00 EST uses the newly starting interval; an event ending exactly at 07:00 excludes that new interval. Zero-duration events are treated as point timestamps.

The mapping selects daily grids overlapping the event. Daily totals cannot isolate precipitation during only the flood-event hours.

### Coverage results

| Check | Result |
| --- | ---: |
| Flood-event records | 125 |
| Required unique PRISM dates | 145 |
| Stored unique PRISM dates | 145 |
| Event-to-date links | 150 |
| Missing required dates | 0 |
| Extra stored dates | 0 |
| Days with all stored cells valid | 145/145 |
| Negative precipitation cells | 0 |
| Events with complete linked grids | 125/125 |

Stored dates range from 1996-01-20 to 2025-07-20. Only selected event-related dates are stored; this is not a continuous daily record across those years. Coverage describes availability, not scientific accuracy.

### Access and demonstration

`prism_access.py` provides `list_events()`, `describe_prism()`, `event_dates(event_id)`, and `get_raster(event_id, date, source="PRISM")`. Raster retrieval includes values, coordinates, units, CRS and interval information.

```python
from prism_access import event_dates, get_raster

available_dates = event_dates(1)
raster = get_raster(1, available_dates[0])
print(raster["units"])
print(raster["values"].shape)
```

`plot_prism_event.py` provides `plot_event(event_id)` and reads the database directly. Daily panels within an event share a color scale; scales may differ across separate event figures.

Event 1 occurred on 1996-01-19, 11:00–13:00 fixed EST. Its linked daily grid is labeled 1996-01-20. The demonstration is `figures/prism_event_001_dc.png`; it displays daily rainfall, not flood extent.

## DC boundary

The boundary was obtained from the DC GIS service:

https://maps2.dcgis.dc.gov/dcgis/rest/services/BaistIndex/MapServer/0

It was requested and checked in EPSG:4269. It supplies context for PRISM maps without masking the rectangular rainfall grid. For NASA processing, the boundary was transformed into the satellite raster CRS; the satellite values themselves were not reprojected.

## Factor B: in-DC precipitation stations

### Discovery and selection

NOAA NCEI GHCN-Daily station metadata and PRCP inventories were searched for stations marked DC. Nineteen candidates had precipitation inventory years overlapping the study years. Two stations with relatively long inventory periods were selected:

| Station ID | Name | Latitude | Longitude | Elevation (m) | Inventory years |
| --- | --- | ---: | ---: | ---: | --- |
| US1DCDC0009 | WASHINGTON 2.0 SSW | 38.8766 | -77.0224 | 3.0 | 2008–2026 |
| US1DCDC0014 | WASHINGTON 5.1 NW | 38.9581 | -77.0817 | 106.4 | 2011–2026 |

Both catalog positions passed a point-in-polygon check against the DC boundary. The station-catalog datum and historical station moves were not independently verified; the location test used catalog longitude/latitude against the NAD83 boundary without an independently established station-datum transformation.

Inventory years do not guarantee continuous reporting. These stations do not cover the earliest events. Other candidates were not incorporated, and the search is not an exhaustive survey of every possible DC precipitation source. Nearby airports were not substituted for physically in-DC stations.

NOAA NCEI is the archive used for these point observations. It is distinct from the NOAA MRMS gridded product assigned to other project versions.

### Retrieval, processing and flags

Station files were downloaded using:

```text
https://www.ncei.noaa.gov/pub/data/ghcn/daily/by_station/STATION_ID.csv.gz
```

PRCP records within the overall event study period plus a one-day calendar buffer were retained. Raw tenths of millimeters were divided by 10. Negative raw values and observations with nonblank quality flags were excluded from usable precipitation and stored as `NaN`.

Raw values, measurement flags, quality flags, source flags, observation-time strings, trace indicators and usability indicators are preserved. A reported zero with a trace flag is not an exact zero. Absent dates and excluded observations are not treated as zero rainfall.

| Station | Stored study-period records |
| --- | ---: |
| US1DCDC0009 | 1,636 |
| US1DCDC0014 | 4,259 |

### Timing limitations

Original station date labels and observation-time strings are retained. Observation times vary, and the imported records do not explicitly encode record-specific UTC offsets. Exact accumulation start/end timestamps and their relationship to flood hours were not established.

No station UTC conversion or exact station–PRISM interval alignment is claimed. Printed date equality does not establish that the two sources measure the same period. Station figures show calendar-date context around events, not rainfall restricted to event hours. The conclusion and supporting references are recorded in `reports/station_time_interpretation.txt` and station-group metadata.

### Access, plots and coverage

`station_access.py` provides `list_stations()` and `get_station_window(event_id, station_id, start_date, end_date)` for inclusive calendar-date windows, including station metadata and missingness information.

`plot_station_event.py` provides `get_station_series(event_id, station_id, buffer_days=3)` and `plot_station_event(event_id)`. Series include missing or excluded dates as `NaN`; plots distinguish missing observations and trace values.

The demonstration uses event 71, 2016-07-19 22:15 through 2016-07-20 01:30 fixed EST, and is saved as `figures/station_event_071.png`. It was chosen for the greatest number of usable nearby records, not the largest rainfall.

Coverage uses original station date labels for each event's calendar dates plus three days before and after:

| Measure | Result |
| --- | ---: |
| Events | 125 |
| Stations | 2 |
| Event–station combinations | 250 |
| Events with at least one usable buffered-window record | 83 (66.4%) |
| Events without usable buffered-window records | 42 (33.6%) |

These counts do not imply complete event coverage or exact accumulation overlap. Yearly reports include study-period dates before the station records began. Gaps can reflect unavailable historical coverage, absent reports or excluded observations.

## Optional NASA surface-water observations

### Product, search and selection

Source: NASA/JPL PO.DAAC, **OPERA DSWx-HLS Version 1**, with native **30 m** pixels in **EPSG:32618 (WGS 84 / UTM zone 18N)**.

Event 124 occurred on 13 July 2025, **18:00–19:05 UTC**. NASA CMR was searched for 10–16 July 2025 over the same geographic bounding box used for PRISM. Seven candidate scenes were returned. Water classification (`B01_WTR`) and cloud-quality (`B09_CLOUD`) layers were downloaded for all seven: 14 files in total.

Coverage was evaluated using DC pixel centers on each native grid. Water classes 0, 1 and 2 were considered usable; cloud/shadow, snow/ice, ocean-masked and missing cells were excluded. Missing/outside-tile coverage was measured against all DC pixel centers, not only the tile intersection.

Two T18SUJ scenes were integrated independently:

| Observation (UTC) | Hours before event start | Usable DC | Cloud/shadow over DC |
| --- | ---: | ---: | ---: |
| Landsat 8, 11 July 2025, 15:45 | 50.24 | 30.78% | 68.70% |
| Sentinel-2C, 13 July 2025, 16:02 | 1.95 | 12.99% | 86.16% |

The Landsat scene had the highest usable DC coverage among the candidates. The Sentinel-2C scene provided closer pre-event context. The only post-event candidate had 0% usable DC coverage.

### Processing, storage and interpretation

Native rectangular raster subsets around DC are stored without resampling or reprojection of values. Each scene retains original water and cloud-quality codes, projected pixel-center coordinates, affine transform, CRS, acquisition timestamps, event association, source URLs, download records, DC mask and usable-DC mask. Search metadata and the seven-scene coverage report are also preserved within HDF5.

The water legend is: 0 = not water; 1 = open water; 2 = partial water; 252 = snow/ice class; 253 = cloud/cloud shadow; 254 = ocean masked; 255 = missing. Original B09 cloud-quality codes are preserved and are not treated as a simple binary mask.

**Both selected scenes precede the flood.** Cloud cover is extensive, and detected water includes permanent water bodies. These scenes provide pre-event surface-water context; they do not establish flood extent or flood-related change. Missing or cloud-obscured pixels are not dry land. Lack of a detection does not prove that flooding did not occur.

### Visualization and verification

`plot_nasa_event.py` reads the saved HDF5 scenes and creates `figures/nasa_event_124_context.png`, with the DC boundary, classification legend, acquisition timing, usable coverage and interpretation caveat.

`verify_nasa_data.py` passed for both integrated scenes. Stored water and cloud arrays match the original raster windows; CRS, native grid alignment, coordinate arrays and usable masks are consistent. Presence of the PRISM precipitation dataset and station group was also checked. This is a storage/processing check, not validation of a satellite flood detection.

## Integrated HDF5 structure

File: `prism_dc_events.h5`

| Path | Contents |
| --- | --- |
| `/dates` | PRISM ending-date labels |
| `/latitude`, `/longitude` | PRISM cell-center coordinates |
| `/precipitation_mm` | PRISM array: date × latitude × longitude |
| `/prism_interval_start_utc`, `/prism_interval_end_utc` | PRISM daily accumulation bounds |
| `/events/event_id` | Original-row-based event identifiers |
| `/events/start_est`, `/events/end_est` | Fixed-EST event timestamps |
| `/event_prism_mapping/event_id` | Event identifiers for date links |
| `/event_prism_mapping/prism_date` | Linked PRISM dates |
| `/event_prism_mapping/prism_date_index` | Zero-based PRISM array indices |
| `/dc_boundary/ring_000` | Boundary coordinates: longitude, latitude |
| `/stations/STATION_ID/date_label` | Original station date labels |
| `/stations/STATION_ID/precipitation_mm` | Usable daily precipitation; excluded values are NaN |
| `/stations/STATION_ID/raw_prcp_tenths_mm` | Original raw PRCP values |
| `/stations/STATION_ID/measurement_flag` | Measurement flags |
| `/stations/STATION_ID/quality_flag` | Quality flags |
| `/stations/STATION_ID/source_flag` | Source flags |
| `/stations/STATION_ID/observation_time_hhmm` | Original observation-time strings |
| `/stations/STATION_ID/trace`, `/stations/STATION_ID/usable` | Trace and usability indicators |
| `/nasa/catalog_json` | NASA search response and search provenance |
| `/nasa/coverage_csv` | Seven-scene coverage report |
| `/nasa/scenes/SCENE_ID/water_class` | Native water-classification subset |
| `/nasa/scenes/SCENE_ID/cloud_quality` | Original cloud-quality subset |
| `/nasa/scenes/SCENE_ID/x`, `/nasa/scenes/SCENE_ID/y` | Projected pixel centers in metres |
| `/nasa/scenes/SCENE_ID/dc_mask` | DC pixel-center mask |
| `/nasa/scenes/SCENE_ID/usable_dc_mask` | Usable water-classification pixels within DC |

Attributes provide source, units, spatial/time semantics, processing and limitations. Event 124 is associated with NASA scenes through metadata; association does not imply temporal overlap. Sources retain their individual grids and time conventions rather than being forced into a common grid or interval.

## Python environment

External packages: `numpy`, `rasterio`, `h5py`, `matplotlib`, and `truststore`.

```bash
python -m pip install numpy rasterio h5py matplotlib truststore
```

Network scripts use system certificate trust through `truststore`; TLS verification is not disabled. Standard-library modules require no separate installation.

The development environment recorded in `reports/environment.txt` was Python **3.14.2** on Windows 11, with:

```text
numpy==2.4.4
rasterio==1.5.2
h5py==3.16.0
matplotlib==3.11.2
truststore==0.10.5
```

Install the recorded direct dependencies with:

```bash
python -m pip install -r requirements.txt
```

`save_environment.py` records Python/platform details and the five direct package versions. This is not a lockfile for all transitive dependencies or system libraries. A full fresh-environment rebuild, including downloads, has not been verified.

## Use the supplied database without downloads

The integrated HDF5 is included. To inspect it and reproduce demonstrations:

```bash
python check_events.py
python prism_access.py
python station_access.py
python prism_coverage.py
python prism_event_coverage.py
python station_event_coverage.py
python plot_prism_event.py
python plot_station_event.py
python plot_nasa_event.py
```

Enter `1` for the PRISM plot prompt. Close each figure before running the next script. Coverage scripts regenerate their reports. Integration scripts are for rebuilding, not routine inspection of the supplied database.

`prism_coverage.py` reads the integrated `prism_dc_events.h5`, so it works with this submission without the intermediate PRISM-only file. The earlier exploration scripts `check_prism.py`, `check_prism_h5.py`, `save_prism_example.py`, and `plot_prism.py` may require excluded raw or intermediate files; they are not part of this quick-start sequence. `verify_nasa_data.py` compares against raw satellite downloads and therefore requires those downloads to have been obtained first.

## Reproduction

Run commands from the project directory with the same Python environment. Keep the original CSV and source scripts together. Downloads require network access. To rebuild safely, use a fresh directory: several integration scripts intentionally stop when their output file or target group already exists.

### Factor A

```bash
python check_events.py
python prism_dates.py
python download_prism.py
python build_prism_h5.py
python add_prism_events.py
python download_dc_boundary.py
python add_dc_boundary.py
python prism_metadata.py
python prism_coverage.py
python prism_event_coverage.py
python prism_access.py
python plot_prism_event.py
```

Use event 1 for the PRISM demonstration if prompted. `prism_dc.h5` is the intermediate PRISM-only file; `prism_dc_events.h5` is the integrated deliverable. Preserve the original and add later sources to the integrated file.

### Factor B

After Factor A and the boundary are present:

```bash
python find_dc_stations.py
python check_station_inventory.py
python check_station_locations.py
python download_station_data.py
python prepare_station_data.py
python add_station_data.py
python station_yearly_coverage.py
python station_event_coverage.py
python station_access.py
python document_station_timing.py
python plot_station_event.py
```

The station demonstration uses event 71. Existing station groups are protected against accidental replacement.

### NASA extension

After the integrated HDF5 and boundary exist:

```bash
python nasa_search.py
python download_nasa.py
python check_nasa_coverage.py
python add_nasa_data.py
python plot_nasa_event.py
python verify_nasa_data.py
```

Downloading requires a NASA Earthdata account. Paste the token only at the hidden terminal prompt in `download_nasa.py`. The script does not write it to project files. Never place credentials in code, screenshots, reports or GitHub. NASA integration stops if `/nasa` already exists.

Close Matplotlib figure windows before starting the next script in the same terminal. Demonstration and read-only access scripts can be run without rebuilding the database or redownloading data.

## Reports and figures

Reports are under `reports/`:

| File | Purpose |
| --- | --- |
| `prism_daily_coverage.csv` | Daily grid coverage and descriptive values |
| `prism_coverage_summary.txt` | PRISM availability and limitations |
| `prism_event_coverage.csv` | Event-to-grid availability |
| `dc_station_candidates.csv` | DC catalog candidates |
| `dc_station_rainfall_inventory.csv` | PRCP inventory search |
| `selected_station_locations.csv` | Selected-station location checks |
| `station_download_log.csv` | Station retrieval provenance |
| `station_yearly_coverage.csv` | Yearly reporting and missingness |
| `station_event_coverage.csv` | Event–station calendar-window coverage |
| `station_event_coverage_summary.txt` | Buffered-window coverage summary |
| `station_time_interpretation.txt` | Station timing interpretation and limitations |
| `nasa_search_event_124.json` | Satellite search response and provenance |
| `nasa_candidates_event_124.csv` | Candidate scenes and timestamps |
| `nasa_download_log.csv` | Satellite retrieval and file-check records |
| `nasa_coverage_event_124.csv` | DC coverage for all seven candidates |
| `nasa_verification.txt` | Stored satellite array/grid checks |

The PRISM coverage report checks availability against the saved mapping. During packaging, all 150 links were additionally checked by independently intersecting daily intervals with the 125 original event records. This verifies the implemented interval convention, not the scientific accuracy of daily precipitation estimates.

Representative figures:

- `figures/prism_event_001_dc.png`
- `figures/station_event_071.png`
- `figures/nasa_event_124_context.png`

## Repository and submission contents

Include source scripts, the original event CSV, this README, actual environment requirements, coverage/validation reports, representative figures, and one integrated processed database, `prism_dc_events.h5`. If repository size limits prevent including the database, provide an approved data-delivery location and reproducible generation instructions; no external database location is claimed here.

Raw PRISM archives, station downloads, satellite downloads, processed intermediate station CSVs and the intermediate PRISM-only HDF5 are rebuild inputs/intermediates rather than additional integrated deliverables. Keep local copies until submission is verified. Exclude large raw downloads, temporary files, duplicate scripts accidentally saved under `reports/`, virtual environments and credentials from the submission repository. Do not delete the reports themselves.

GitHub publication and a fresh-directory rebuild are not established by this README; verify them during final packaging.

## Scientific limitations

- PRISM is a modeled precipitation estimate, not a direct measurement in every cell.
- Full daily rainfall totals cannot resolve rainfall during short flood-event hours.
- PRISM rectangle statistics are not DC-only statistics.
- Station reporting is incomplete and does not cover all historical events.
- Station date labels and variable observation times do not establish exact accumulation intervals or temporal equivalence to PRISM.
- Station location checks rely on catalog coordinates, with datum/history limitations stated above.
- NASA images are cloudy pre-event observations, not confirmed flood-extent maps.
- Coverage and storage checks do not establish source accuracy, causal relationships or predictive performance.

## Sources and documentation

### PRISM

- https://prism.oregonstate.edu/documents/PRISM_datasets.pdf
- https://prism.oregonstate.edu/formats/
- https://prism.oregonstate.edu/faq/
- https://services.nacse.org/prism/data/get/us/800m/ppt/YYYYMMDD

### Stations

- https://www.ncei.noaa.gov/pub/data/ghcn/daily/ghcnd-stations.txt
- https://www.ncei.noaa.gov/pub/data/ghcn/daily/ghcnd-inventory.txt
- https://www.ncei.noaa.gov/pub/data/ghcn/daily/readme.txt
- https://www.ncei.noaa.gov/pub/data/ghcn/daily/readme-by_station.txt
- https://www.ncei.noaa.gov/pub/data/ghcn/daily/by_station/

### Boundary

- https://maps2.dcgis.dc.gov/dcgis/rest/services/BaistIndex/MapServer/0

### NASA

- https://podaac.jpl.nasa.gov/dataset/OPERA_L3_DSWX-HLS_V1
- https://www.jpl.nasa.gov/go/opera/products/dswx-product-suite/
- https://cmr.earthdata.nasa.gov/search/granules.json
- https://archive.podaac.earthdata.nasa.gov/podaac-ops-cumulus-docs/web-misc/opera/OPERA_DSWx-HLS_ProductSpec_v1.0.0_D-107395_RevB.pdf

Exact search parameters, scene identifiers, source links and available retrieval records are preserved in the generated metadata and reports. Source revisions or future archive changes may affect a later download.

## AI assistance acknowledgment

OpenAI ChatGPT assisted with translation and English wording, as English is not my first language, explaining project requirements, reviewing and correcting code, and guidance on the optional NASA section.