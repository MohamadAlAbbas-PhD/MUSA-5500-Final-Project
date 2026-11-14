# Where Malaria, Open Defecation, and Child Anemia Coincide

**A geospatial typology of DHS clusters in sub-Saharan Africa**
MUSA 5500 Geospatial Data Science in Python · Final project · Mohamad AlAbbas · Fall 2026

🌍 **Website:** https://mohamadalabbas-phd.github.io/MUSA-5500-Final-Project/

## What's here

| Path | What it is |
|---|---|
| `analysis/01_build_clusters.py` | DHS child records → one row per survey cluster (pandas) |
| `analysis/02_raster_features.py` | Buffers + zonal statistics: Malaria Atlas Project malaria and CHIRPS rainfall anomalies (rasterio, rasterstats, xarray) |
| `analysis/03_download_boundaries.py` | Admin-1 boundaries from the geoBoundaries API |
| `analysis/04_profiles_hotspots.py` | k-means profiles + DBSCAN hotspots (scikit-learn) |
| `analysis/05_predict_anemia.py` | Random forest vs. linear regression, CV, grid search, spatial lag (scikit-learn) |
| `analysis/06_public_outputs.py` | Aggregates results to hexagons and regions for publication (h3, geopandas) |
| `data/public/` | **Aggregated, non-identifying** outputs used by the website |
| `*.qmd`, `_quarto.yml`, `_common.py`, `_maps.py` | Quarto website source (folium maps, Altair linked charts) |
| `docs/` | Rendered website (served by GitHub Pages) |

## Course requirements met

1. **Raster analysis** with rasterio, rasterstats, and xarray (MAP malaria and CHIRPS rainfall, zonal statistics over buffers)
2. **Clustering** with scikit-learn (k-means profiles, DBSCAN hotspots)
3. **Machine learning** with scikit-learn (random forest vs. linear regression, cross-validation, grid search)
4. **Data from 3+ sources**: DHS surveys, DHS GPS, Malaria Atlas Project, CHIRPS, geoBoundaries
5. **Data collected through APIs**: MAP Web Coverage Service and the geoBoundaries API
6. **Multiple interactive visualizations**: cross-filtering, brushing, legend selection, sliders, drop-downs, toggleable map layers

## Data and privacy

The DHS microdata and GPS coordinates are **not included** in this repository, because DHS terms of use do not allow redistribution. Cluster-level files are excluded by `.gitignore`. To reproduce the analysis:

1. Register at [dhsprogram.com](https://dhsprogram.com/data/new-user-registration.cfm) and request access to the surveys and GPS datasets, then create an extract at [IPUMS-DHS](https://www.idhsdata.org/) with the variables listed in `analysis/01_build_clusters.py`.
2. Download CHIRPS monthly rainfall from the [Climate Hazards Center](https://www.chc.ucsb.edu/data/chirps). The Malaria Atlas Project rasters can be downloaded from the [MAP data portal](https://data.malariaatlas.org).
3. Set the paths in `analysis/config.py`.

## Run it

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows  (source .venv/bin/activate on Mac/Linux)
pip install -r requirements.txt
cd analysis
python 01_build_clusters.py && python 02_raster_features.py && python 03_download_boundaries.py
python 04_profiles_hotspots.py && python 05_predict_anemia.py && python 06_public_outputs.py
cd ..
quarto render                   # writes the site to docs/
```

## Data credits

- DHS Program / IPUMS-DHS (Boyle, King & Sobek, IPUMS-DHS, Minneapolis, MN: IPUMS and ICF)
- Malaria Atlas Project, *P. falciparum* parasite rate, 2026 release (2000–2025) (CC BY 4.0)
- Funk et al. (2015), CHIRPS rainfall, Climate Hazards Center, UC Santa Barbara
- Runfola et al. (2020), geoBoundaries (CC BY 4.0)
