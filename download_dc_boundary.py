import json
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

import truststore

truststore.inject_into_ssl()

project_dir = Path(__file__).resolve().parent
output_file = project_dir / "dc_boundary.json"

# Official DC GIS boundary service
service_url = (
    "https://maps2.dcgis.dc.gov/dcgis/rest/services/"
    "BaistIndex/MapServer/0/query"
)

# Request the boundary in the same CRS as our PRISM grids.
parameters = {
    "where": "1=1",
    "outFields": "CITY_NAME",
    "returnGeometry": "true",
    "outSR": "4269",
    "f": "json",
}

url = service_url + "?" + urlencode(parameters)

print("Downloading DC boundary...", flush=True)

with urlopen(url, timeout=120) as response:
    boundary = json.load(response)

if "error" in boundary:
    raise RuntimeError(boundary["error"])

features = boundary.get("features", [])

if not features:
    raise ValueError("The service returned no boundary features.")

for feature in features:
    if not feature.get("geometry", {}).get("rings"):
        raise ValueError("The boundary geometry is missing.")

boundary["retrieval_url"] = url
boundary["source"] = "District of Columbia GIS"
boundary["requested_crs"] = "EPSG:4269"

output_file.write_text(
    json.dumps(boundary, indent=2),
    encoding="utf-8",
)

print("Finished! Saved:", output_file.name)
print("Boundary features:", len(features))
print("Requested CRS: EPSG:4269")