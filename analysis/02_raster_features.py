"""Step 2. Add raster-based features to each cluster (zonal statistics).

  * Buffers: 2 km (urban) / 5 km (rural), matching DHS GPS displacement.
  * Malaria: Malaria Atlas Project P. falciparum prevalence (age 2-10),
             mean over the buffer, for the cluster's interview year.
  * Rainfall: CHIRPS monthly. Total rain in the 3 months before the interview
              month, as a standardized anomaly (z-score) against the same
              3 calendar months in 1981-2010 at that location.
              Plus the long-term (1981-2010) mean annual rainfall.

Input : data/private/clusters.parquet
Output: data/private/clusters_features.parquet
"""
import numpy as np
import pandas as pd
import geopandas as gpd
import rasterio
import xarray as xr
from rasterio.transform import from_origin
from rasterstats import zonal_stats
from config import PRIVATE, CHIRPS_MONTHLY, MAP_DIR, AFRICA_BBOX, AFRICA_EQUAL_AREA

cl = pd.read_parquet(PRIVATE / "clusters.parquet")
pts = gpd.GeoDataFrame(cl, geometry=gpd.points_from_xy(cl.lon, cl.lat), crs="EPSG:4326")

# ---- buffers (in metres, using an equal-area projection) ------------------
pts_m = pts.to_crs(AFRICA_EQUAL_AREA)
radius = np.where(pts_m.urban == 1, 2000, 5000)
buf = pts_m.buffer(radius).to_crs("EPSG:4326")
print(f"{len(buf):,} buffers built")

def zonal_mean(geoms, array, transform, nodata):
    out = zonal_stats(list(geoms), array, affine=transform, stats=["mean"],
                      nodata=nodata, all_touched=True)
    return np.array([o["mean"] if o["mean"] is not None else np.nan for o in out])

# ---- malaria (MAP PfPR 2-10), matched to interview year --------------------
cl["pfpr"] = np.nan
for yr, idx in cl.groupby(cl.int_year.clip(2000, 2021)).groups.items():
    with rasterio.open(MAP_DIR / f"PfPR_2-10_Africa_{yr}.tif") as src:
        arr = src.read(1).astype("float32")
        nod = src.nodata
        if nod is not None:
            arr[arr == nod] = np.nan
        arr[arr < 0] = np.nan
        cl.loc[idx, "pfpr"] = zonal_mean(buf.loc[idx], arr, src.transform, np.nan) * 100
    print(f"  malaria {yr}: {len(idx):,} clusters")

# ---- rainfall (CHIRPS monthly) --------------------------------------------
lon0, lat0, lon1, lat1 = AFRICA_BBOX
YEARS = range(1981, 2022)
BASE = (1981, 2010)

def open_year(y):
    ds = xr.open_dataset(CHIRPS_MONTHLY / f"CHIRPS_monthly_{y}.nc")
    return ds["precip"].sel(longitude=slice(lon0, lon1), latitude=slice(lat1, lat0))

# load all years once (Africa subset), as a dict of (12, ny, nx) float32 arrays
print("Loading CHIRPS (Africa subset)...")
rain = {}
for y in range(YEARS.start - 1, YEARS.stop):
    try:
        da = open_year(y)
    except FileNotFoundError:
        continue
    rain[y] = da.values.astype("float32")
    lats, lons = da.latitude.values, da.longitude.values
res = abs(float(lons[1] - lons[0]))
transform = from_origin(lons.min() - res / 2, lats.max() + res / 2, res, res)

def three_month_total(y, end_month):
    """Rain total for the 3 months ending in end_month (1-12) of year y."""
    tot = 0
    for k in range(3):
        m, yy = end_month - k, y
        if m <= 0:
            m, yy = m + 12, y - 1
        if yy not in rain:
            return None
        tot = tot + rain[yy][m - 1]
    return tot

# long-term mean annual rainfall (1981-2010)
annual = np.nanmean([rain[y].sum(axis=0) for y in range(BASE[0], BASE[1] + 1)], axis=0)
cl["rain_annual_mm"] = zonal_mean(buf, annual, transform, np.nan)

# 3-month anomaly: window ends the month BEFORE the interview month
end = cl.int_month - 1
end_year = np.where(end == 0, cl.int_year - 1, cl.int_year)
end = np.where(end == 0, 12, end)
cl["rain_end_month"], cl["rain_end_year"] = end, end_year
cl["rain_3mo_mm"] = np.nan
cl["rain_3mo_z"] = np.nan

for e in range(1, 13):
    base = [three_month_total(y, e) for y in range(BASE[0], BASE[1] + 1)]
    base = np.stack([b for b in base if b is not None])     # 1981 Jan/Feb windows need 1980 (no data)
    mu, sd = base.mean(axis=0), base.std(axis=0)
    sd[sd < 1] = np.nan                        # near-zero variability (desert) -> undefined
    for y in sorted(set(end_year[end == e])):
        idx = cl.index[(end == e) & (end_year == y)]
        tot = three_month_total(y, e)
        z = np.clip((tot - mu) / sd, -5, 5)
        cl.loc[idx, "rain_3mo_mm"] = zonal_mean(buf.loc[idx], tot, transform, np.nan)
        cl.loc[idx, "rain_3mo_z"] = zonal_mean(buf.loc[idx], z, transform, np.nan)
    print(f"  rainfall window ending month {e:2d} done")

cl.to_parquet(PRIVATE / "clusters_features.parquet", index=False)
print(cl[["pfpr", "rain_annual_mm", "rain_3mo_mm", "rain_3mo_z"]].describe().round(2).to_string())
print("Missing:", cl[["pfpr", "rain_3mo_z"]].isna().sum().to_dict())
