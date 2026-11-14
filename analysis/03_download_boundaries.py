"""Step 3. Download admin-1 (region/province) boundaries from the geoBoundaries API.

Source: geoBoundaries (www.geoboundaries.org), open licence, CC BY 4.0.
Output: data/public/admin1.geojson  (public data, safe to commit)
"""
import json
import time
import urllib.request
import geopandas as gpd
import pandas as pd
from config import PUBLIC, PRIVATE, SSA, ISO3

name_to_code = {v: k for k, v in SSA.items()}
countries = pd.read_parquet(PRIVATE / "clusters.parquet", columns=["country"]).country.unique()

def get_json(url, tries=4):
    for i in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=120) as r:
                return json.loads(r.read())
        except Exception as e:
            print(f"    retry {i + 1}: {e}")
            time.sleep(2 ** i)
    raise RuntimeError(url)

frames = []
for c in sorted(countries):
    iso = ISO3[name_to_code[c]]
    meta = get_json(f"https://www.geoboundaries.org/api/current/gbOpen/{iso}/ADM1/")
    g = gpd.read_file(meta["simplifiedGeometryGeoJSON"])
    g = g[["shapeName", "geometry"]].rename(columns={"shapeName": "region"})
    g["country"], g["iso3"] = c, iso
    frames.append(g)
    print(f"  {c:15s} {iso}: {len(g)} regions")

adm = pd.concat(frames, ignore_index=True).to_crs("EPSG:4326")
adm["region_id"] = adm.iso3 + "_" + adm.groupby("iso3").cumcount().astype(str).str.zfill(3)
adm["geometry"] = adm.geometry.make_valid().simplify(0.01, preserve_topology=True)
adm[["region_id", "region", "country", "iso3", "geometry"]].to_file(PUBLIC / "admin1.geojson", driver="GeoJSON")
print(f"Saved {len(adm)} regions")
