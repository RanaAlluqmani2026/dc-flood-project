import platform
from importlib.metadata import version
from pathlib import Path

project_dir = Path(__file__).resolve().parent
reports_dir = project_dir / "reports"
reports_dir.mkdir(exist_ok=True)

packages = [
    "numpy",
    "rasterio",
    "h5py",
    "matplotlib",
    "truststore",
]

requirements = [
    f"{package}=={version(package)}"
    for package in packages
]

(project_dir / "requirements.txt").write_text(
    "\n".join(requirements) + "\n",
    encoding="utf-8",
)

environment = [
    f"Python: {platform.python_version()}",
    f"Platform: {platform.platform()}",
    "",
    *requirements,
]

(reports_dir / "environment.txt").write_text(
    "\n".join(environment) + "\n",
    encoding="utf-8",
)

print("\n".join(environment))
print("\nSaved: requirements.txt")
print("Saved: reports/environment.txt")