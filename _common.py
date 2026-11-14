"""Shared loaders, colours and labels for the website pages (public data only)."""
import json
from pathlib import Path
import pandas as pd
import geopandas as gpd
import altair as alt
import shapely

PUB = Path("data/public")
alt.data_transformers.disable_max_rows()

PROFILE_COLORS = {
    "All three high": "#b2182b",
    "High anemia + malaria": "#7b3294",
    "High open defecation": "#bf812d",
    "High anemia": "#f4a582",
    "All three low": "#5aae61",
}
PROFILE_ORDER = list(PROFILE_COLORS)
PROFILE_TEXT = {
    "All three high": "Most children anemic, most households without a toilet, and heavy malaria.",
    "High anemia + malaria": "Anemia tracks malaria here; most households do have a toilet.",
    "High open defecation": "Toilets are rare, but malaria is low and anemia is closer to average.",
    "High anemia": "Anemia is common even though toilets are common and malaria is low.",
    "All three low": "The best-off places: lower anemia, toilets, little malaria.",
}
VAR = {  # column: (label, colour scheme, domain)
    "anemia_pct": ("Children anemic (%)", "reds", [20, 95]),
    "od_pct": ("Households with no toilet (%)", "yelloworangebrown", [0, 100]),
    "pfpr": ("Malaria prevalence, age 2-10 (%)", "purples", [0, 70]),
    "rain_3mo_z": ("Rainfall anomaly, 3 months before survey (SD)", "brownbluegreen", [-2, 2]),
    "rain_annual_mm": ("Typical annual rainfall (mm)", "blues", [200, 2500]),
    "wealth": ("Average wealth quintile (1 poorest - 5 richest)", "greens", [1, 5]),
    "abs_err": ("Model error (percentage points)", "oranges", [5, 30]),
    "resid": ("Actual minus predicted anemia (pp)", "redblue", [-15, 15]),
}

def summary():
    return json.load(open(PUB / "sample_summary.json"))

def _cw(g):
    """Altair/d3 expects clockwise outer rings (the opposite of GeoJSON's convention)."""
    g["geometry"] = shapely.orient_polygons(g.geometry.values, exterior_cw=True)
    return g


def hexes():
    return _cw(gpd.read_file(PUB / "hexes.geojson"))

def regions(simplify=0.03):
    g = gpd.read_file(PUB / "regions.geojson")
    g["geometry"] = g.geometry.simplify(simplify, preserve_topology=True)
    return _cw(g)

def csv(name):
    return pd.read_csv(PUB / name)

def profile_scale():
    return alt.Scale(domain=PROFILE_ORDER, range=list(PROFILE_COLORS.values()))
