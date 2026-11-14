"""Step 1. Turn DHS child records into one row per survey cluster.

Input : IPUMS-DHS extract (private)
Output: data/private/clusters.parquet  (private: contains GPS)
"""
import numpy as np
import pandas as pd
import pyreadstat
from config import DHS_FILE, PRIVATE, SSA, MIN_CHILDREN

cols = ["sample", "country", "year", "idhspsu", "intyear", "monthint", "urban",
        "wealthq", "educlvl", "kidalive", "kidagemo", "anemialvlkid",
        "opentoiletpsu", "gpslat", "gpslong", "perweight"]

print("Reading DHS extract (this takes a few minutes)...")
d, meta = pyreadstat.read_dta(str(DHS_FILE), usecols=cols)
print(f"  {len(d):,} child records, {d.country.nunique()} countries")

flow = [("All child records", len(d))]
def keep(mask, label):
    global d
    d = d[mask]
    flow.append((label, len(d)))

keep(d.country.isin(SSA.keys()), "Sub-Saharan Africa")
keep(d.kidalive == 1, "Child alive")
keep(d.kidagemo.between(6, 59), "Aged 6-59 months")
keep(d.anemialvlkid.isin([1, 2, 3, 4]), "Tested for anemia")
ok_gps = d.gpslat.notna() & d.gpslong.notna() & ~((d.gpslat == 0) & (d.gpslong == 0))
keep(ok_gps, "Cluster has GPS coordinates")
keep(d.opentoiletpsu.between(0, 100), "Cluster open defecation share available")
keep(d.urban.isin([1, 2]), "Urban/rural known")

d["anemic"] = (d.anemialvlkid <= 3).astype(float)            # any anemia (Hb < 11 g/dL, altitude-adjusted)
d["mod_sev"] = (d.anemialvlkid <= 2).astype(float)          # moderate or severe
d["mom_secondary"] = np.where(d.educlvl.isin([0, 1, 2, 3]), (d.educlvl >= 2).astype(float), np.nan)
d["country_name"] = d.country.map(SSA)
d["wealthq_ok"] = d.wealthq.where(d.wealthq.between(1, 5))

g = d.groupby("idhspsu")
cl = pd.DataFrame({
    "sample": g["sample"].first(),
    "country": g["country_name"].first(),
    "survey_year": g["year"].first(),
    "int_year": g["intyear"].agg(lambda s: s.mode().iat[0]).astype(int),
    "int_month": g["monthint"].agg(lambda s: s.mode().iat[0]).astype(int),
    "urban": (g["urban"].first() == 1).astype(int),
    "lat": g["gpslat"].first(),
    "lon": g["gpslong"].first(),
    "n_children": g.size(),
    "anemia_pct": g["anemic"].mean() * 100,
    "modsev_anemia_pct": g["mod_sev"].mean() * 100,
    "od_pct": g["opentoiletpsu"].first(),
    "wealth": g["wealthq_ok"].mean(),       # mean household wealth quintile, 1 = poorest, 5 = richest (relative to own country)
    "mom_secondary_pct": g["mom_secondary"].mean() * 100,
}).reset_index()

n_before = len(cl)
cl = cl[cl.n_children >= MIN_CHILDREN].copy()
flow.append((f"Children in clusters with >= {MIN_CHILDREN} tested children", int(cl.n_children.sum())))

cl.to_parquet(PRIVATE / "clusters.parquet", index=False)
pd.DataFrame(flow, columns=["step", "remaining"]).to_csv(PRIVATE / "sample_flow.csv", index=False)

print(pd.DataFrame(flow, columns=["step", "remaining"]).to_string(index=False))
print(f"Clusters: {n_before:,} -> {len(cl):,} kept; {cl.country.nunique()} countries; "
      f"{cl['sample'].nunique()} surveys; years {cl.int_year.min()}-{cl.int_year.max()}")
print(cl.groupby("country").size().sort_values(ascending=False).to_string())
print(cl[["anemia_pct", "od_pct", "wealth", "mom_secondary_pct", "n_children"]].describe().round(2).to_string())
