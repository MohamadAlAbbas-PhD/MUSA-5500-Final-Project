"""Copy the public (aggregated) exports the story website reads into website/assets/."""
import shutil
from pathlib import Path

root = Path(__file__).resolve().parents[1]
src, dst = root / "data" / "public", root / "website" / "assets"
dst.mkdir(exist_ok=True)
for name in ["hexes.geojson", "regions.geojson", "sample_summary.json", "raster_bounds.json",
             "kmeans_profiles.csv", "profiles_by_country.csv", "dbscan_sensitivity.csv", "dbscan_summary.csv",
             "raster_malaria_2005.png", "raster_malaria_2020.png", "raster_rain_annual.png"]:
    shutil.copy2(src / name, dst / name)
    print("copied", name)
