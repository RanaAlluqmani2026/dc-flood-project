import truststore
truststore.inject_into_ssl()
import csv
import shutil
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

project_dir = Path(__file__).parent
dates_file = project_dir / "prism_event_dates.csv"
download_dir = project_dir / "prism_downloads"
download_dir.mkdir(exist_ok=True)

with dates_file.open(newline="", encoding="utf-8") as file:
    dates = sorted({row["prism_date"] for row in csv.DictReader(file)})

# Reuse the file already downloaded manually.
example_file = project_dir / "prism_ppt_us_30s_19960120.zip"
example_destination = download_dir / example_file.name

if example_file.exists() and not example_destination.exists():
    shutil.copy2(example_file, example_destination)

failed = []

for number, date in enumerate(dates, start=1):
    date_code = date.replace("-", "")
    destination = download_dir / f"prism_ppt_us_30s_{date_code}.zip"
    partial = destination.with_suffix(".part")
    url = f"https://services.nacse.org/prism/data/get/us/800m/ppt/{date_code}"

    if destination.exists() and zipfile.is_zipfile(destination):
        print(f"{number}/{len(dates)}: {date} already downloaded", flush=True)
        continue

    try:
        print(f"{number}/{len(dates)}: downloading {date}...", flush=True)

        request = urllib.request.Request(
            url,
            headers={"User-Agent": "DC-Flood-Project/1.0"}
        )

        with urllib.request.urlopen(request, timeout=120) as response:
            with partial.open("wb") as output:
                shutil.copyfileobj(response, output)

        if not zipfile.is_zipfile(partial):
            raise ValueError("Downloaded file is not a valid ZIP archive.")

        partial.replace(destination)
        print(f"  Saved {destination.name}", flush=True)

    except (OSError, urllib.error.URLError, ValueError) as error:
        failed.append((date, str(error)))
        print(f"  Download failed: {error}", flush=True)
        if partial.exists():
            partial.unlink()

    time.sleep(1)

print("\nDownloads finished.")
print(f"Failed dates: {len(failed)}")
for date, error in failed:
    print(f"{date}: {error}")