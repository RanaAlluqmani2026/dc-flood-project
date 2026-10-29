import csv
import getpass
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlparse
from urllib.request import (
    HTTPRedirectHandler,
    Request,
    build_opener,
)

import rasterio
import truststore

truststore.inject_into_ssl()

# Locate the project even if this script is saved inside reports.
script_dir = Path(__file__).resolve().parent

if script_dir.name.lower() == "reports":
    project_dir = script_dir.parent
else:
    project_dir = script_dir

reports_dir = project_dir / "reports"
download_dir = project_dir / "nasa_downloads"

catalog_file = reports_dir / "nasa_search_event_124.json"
log_file = reports_dir / "nasa_download_log.csv"

if not catalog_file.exists():
    raise FileNotFoundError(
        f"NASA search file was not found:\n{catalog_file}"
    )

download_dir.mkdir(exist_ok=True)

with catalog_file.open(encoding="utf-8") as file:
    catalog = json.load(file)

entries = catalog["catalog_response"]["feed"]["entry"]

# Water classification and cloud-quality layers.
suffixes = ("_B01_WTR.tif", "_B09_CLOUD.tif")
files = {}

for entry in entries:
    for link in entry.get("links", []):
        url = link.get("href", "")
        parsed = urlparse(url)

        if (
            parsed.scheme == "https"
            and parsed.hostname == "archive.podaac.earthdata.nasa.gov"
            and parsed.path.endswith(suffixes)
        ):
            files[url] = entry["title"]

if not files:
    raise RuntimeError("No matching NASA data links found.")


class SafeRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        redirected = super().redirect_request(
            req, fp, code, msg, headers, newurl
        )

        if redirected is not None:
            # Do not forward the token to a different host.
            if (
                urlparse(newurl).hostname
                != urlparse(req.full_url).hostname
            ):
                redirected.remove_header("Authorization")

        return redirected


opener = build_opener(SafeRedirect())

fieldnames = [
    "scene_id",
    "filename",
    "source_url",
    "checked_utc",
    "status",
    "bytes",
    "crs",
    "width",
    "height",
]

print(f"Project folder: {project_dir}")
print(f"Files to check/download: {len(files)}")

token = getpass.getpass(
    "Paste NASA token, then press Enter: "
).strip()

if not token:
    raise RuntimeError("No token entered.")

completed = 0

for number, (url, scene_id) in enumerate(files.items(), start=1):
    filename = Path(urlparse(url).path).name
    destination = download_dir / filename
    temporary = destination.with_suffix(".tif.part")

    print(f"\n[{number}/{len(files)}] {filename}", flush=True)

    try:
        status = "existing_file_checked"

        if not destination.exists():
            request = Request(
                url,
                headers={"Authorization": f"Bearer {token}"},
            )

            with opener.open(request, timeout=180) as response:
                with temporary.open("wb") as output:
                    shutil.copyfileobj(response, output)

            # Ensure the downloaded response is a readable raster.
            with rasterio.open(temporary) as dataset:
                dataset.read(1)

            temporary.replace(destination)
            status = "downloaded"

        with rasterio.open(destination) as dataset:
            dataset.read(1)

            row = {
                "scene_id": scene_id,
                "filename": filename,
                "source_url": url,
                "checked_utc": datetime.now(timezone.utc).isoformat(),
                "status": status,
                "bytes": destination.stat().st_size,
                "crs": str(dataset.crs),
                "width": dataset.width,
                "height": dataset.height,
            }

        needs_header = (
            not log_file.exists()
            or log_file.stat().st_size == 0
        )

        with log_file.open("a", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=fieldnames)

            if needs_header:
                writer.writeheader()

            writer.writerow(row)

        completed += 1
        print(f"OK: {row['bytes'] / 1_000_000:.2f} MB", flush=True)

    except HTTPError as error:
        temporary.unlink(missing_ok=True)
        print(f"Stopped: HTTP {error.code}")
        print("Share the error number only, never your token.")
        break

    except Exception as error:
        temporary.unlink(missing_ok=True)
        print(f"Stopped: {type(error).__name__}")
        print("The current file could not be downloaded or validated.")
        break

print(f"\nFiles successfully checked: {completed}/{len(files)}")

if completed == len(files):
    print("All NASA files downloaded and checked.")
    print("Next: assess DC coverage and cloud-quality classes.")
else:
    print("Download is incomplete.")