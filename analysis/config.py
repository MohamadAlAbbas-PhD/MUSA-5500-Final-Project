"""Shared paths and settings for the analysis scripts.

Private DHS-derived files go to data/private/ (gitignored).
Only aggregated, non-identifying outputs go to data/public/.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PRIVATE = ROOT / "data" / "private"
PUBLIC = ROOT / "data" / "public"
PRIVATE.mkdir(parents=True, exist_ok=True)
PUBLIC.mkdir(parents=True, exist_ok=True)

DHS_FILE = Path(r"C:/Users/malab/Desktop/MUSA-5500-Geospatial-Data-Science-Python-main/Community_San_fresh/data.dta")
ENV = Path(r"D:/0. Environmental Datasets")
CHIRPS_MONTHLY = ENV / "CHIRPS" / "Monthly"      # CHIRPS_monthly_YYYY.nc, 0.05 deg
MAP_DIR = ENV / "MAP" / "PfPR"                    # PfPR_2-10_Africa_YYYY.tif, 5 km

# Africa bounding box (lon_min, lat_min, lon_max, lat_max)
AFRICA_BBOX = (-20, -35, 52, 25)

# Sub-Saharan African countries (IPUMS-DHS country codes = ISO numeric)
SSA = {
    24: "Angola", 108: "Burundi", 120: "Cameroon", 140: "Central African Republic",
    148: "Chad", 174: "Comoros", 178: "Congo Brazzaville", 180: "Congo Democratic Republic",
    204: "Benin", 231: "Ethiopia", 232: "Sierra Leone", 266: "Gabon", 270: "Gambia",
    288: "Ghana", 324: "Guinea", 384: "Cote d'Ivoire", 404: "Kenya", 426: "Lesotho",
    430: "Liberia", 450: "Madagascar", 454: "Malawi", 466: "Mali", 478: "Mauritania",
    508: "Mozambique", 516: "Namibia", 562: "Niger", 566: "Nigeria", 646: "Rwanda",
    678: "Sao Tome and Principe", 686: "Senegal", 710: "South Africa", 716: "Zimbabwe",
    729: "Sudan", 748: "Eswatini", 768: "Togo", 800: "Uganda", 834: "Tanzania",
    854: "Burkina Faso", 894: "Zambia",
}

# ISO3 codes (for downloading boundaries)
ISO3 = {
    24: "AGO", 108: "BDI", 120: "CMR", 140: "CAF", 148: "TCD", 174: "COM", 178: "COG",
    180: "COD", 204: "BEN", 231: "ETH", 232: "SLE", 266: "GAB", 270: "GMB", 288: "GHA",
    324: "GIN", 384: "CIV", 404: "KEN", 426: "LSO", 430: "LBR", 450: "MDG", 454: "MWI",
    466: "MLI", 478: "MRT", 508: "MOZ", 516: "NAM", 562: "NER", 566: "NGA", 646: "RWA",
    678: "STP", 686: "SEN", 710: "ZAF", 716: "ZWE", 729: "SDN", 748: "SWZ", 768: "TGO",
    800: "UGA", 834: "TZA", 854: "BFA", 894: "ZMB",
}

# Equal-area projection for Africa (metres), used for buffers
AFRICA_EQUAL_AREA = "ESRI:102022"   # Africa Albers Equal Area Conic

MIN_CHILDREN = 5    # clusters with fewer tested children are dropped (too noisy)
