"""Folium map builders for the website (public, aggregated data only)."""
import json
import numpy as np
import branca.colormap as bcm
import folium
from folium.plugins import Fullscreen
from jinja2 import Template
from branca.element import MacroElement
from _common import PUB, PROFILE_COLORS, hexes, regions

# measures the hex layer can show: column -> (label, colormap, vmin, vmax, unit)
MEASURES = {
    "anemia_pct": ("Children with anemia", ["#fee5d9", "#fcae91", "#fb6a4a", "#de2d26", "#a50f15"], 20, 95, "%"),
    "od_pct": ("Households with no toilet (open defecation)", ["#ffffd4", "#fed98e", "#fe9929", "#d95f0e", "#993404"], 0, 100, "%"),
    "pfpr": ("Malaria prevalence, children 2-10", ["#f2f0f7", "#cbc9e2", "#9e9ac8", "#756bb1", "#54278f"], 0, 70, "%"),
    "rain_3mo_z": ("Rainfall anomaly before survey (dry ← → wet)", ["#8c510a", "#d8b365", "#f5f5f5", "#5ab4ac", "#01665e"], -2, 2, " SD"),
    "rain_annual_mm": ("Typical annual rainfall", ["#f7fbff", "#c6dbef", "#6baed6", "#2171b5", "#08306b"], 200, 2500, " mm"),
    "wealth": ("Average household wealth quintile", ["#edf8e9", "#bae4b3", "#74c476", "#31a354", "#006d2c"], 1, 5, ""),
    "abs_err": ("Prediction error of the model", ["#feedde", "#fdbe85", "#fd8d3c", "#e6550d", "#a63603"], 5, 30, " pp"),
}


def _colormap(key):
    label, cols, lo, hi, unit = MEASURES[key]
    return bcm.LinearColormap(cols, vmin=lo, vmax=hi)


def _legend_html(key):
    label, cols, lo, hi, unit = MEASURES[key]
    grad = ", ".join(cols)
    return (f"<b>{label}</b><div style='height:10px;width:180px;background:linear-gradient(to right,{grad});"
            f"border-radius:3px;margin:4px 0'></div><div style='display:flex;justify-content:space-between;"
            f"width:180px;font-size:11px'><span>{lo}{unit}</span><span>{hi}{unit}</span></div>")


def _profile_legend():
    items = "".join(f"<div><span style='display:inline-block;width:11px;height:11px;background:{c};"
                    f"margin-right:5px;border-radius:2px'></span>{n}</div>" for n, c in PROFILE_COLORS.items())
    return f"<b>Cluster profile (k-means)</b>{items}"


def hex_features(cols_extra=()):
    """Hex GeoDataFrame with a pre-computed fill colour for every measure (c_<col>)."""
    hx = hexes()
    for k in MEASURES:
        cm = _colormap(k)
        hx[f"c_{k}"] = [cm(min(max(v, cm.vmin), cm.vmax)) if v == v else "#cccccc" for v in hx[k]]
    hx["c_profile"] = hx.profile_name.map(PROFILE_COLORS)
    hx["c_hotspot"] = np.where(hx.hotspot_id > 0, "#b2182b", "#dddddd")
    hx["period"] = hx.year_min.astype(int).astype(str) + "–" + hx.year_max.astype(int).astype(str)
    hx["geometry"] = hx.geometry.set_precision(0.001)
    return hx


TOOLTIP_FIELDS = ["country", "profile_name", "n_clusters", "anemia_pct", "od_pct", "pfpr",
                  "rain_3mo_z", "wealth", "pred_anemia_pct", "period"]
TOOLTIP_ALIASES = ["Country", "Most common profile", "DHS clusters", "Children anemic (%)",
                   "No toilet (%)", "Malaria (%)", "Rain anomaly (SD)", "Wealth quintile",
                   "Model-predicted anemia (%)", "Surveys"]


class MeasurePanel(MacroElement):
    """Leaflet control: pick the hex measure, zoom to a country, set opacity."""
    _template = Template("""
    {% macro script(this, kwargs) %}
    (function() {
      var map = {{ this.map_name }}, layer = {{ this.layer_name }};
      var legends = {{ this.legends }}, bounds = {{ this.bounds }}, measures = {{ this.measures }};
      var current = "{{ this.default }}", opacity = 0.75;
      function restyle() {
        layer.setStyle(function(f) {
          return {fillColor: f.properties["c_" + current], fillOpacity: opacity, color: "#ffffff", weight: 0.4};
        });
        document.getElementById("{{ this.uid }}-legend").innerHTML = legends[current];
      }
      var ctl = L.control({position: "topright"});
      ctl.onAdd = function() {
        var d = L.DomUtil.create("div", "leaflet-bar");
        d.style.cssText = "background:white;padding:8px 10px;font:12px/1.35 sans-serif;max-width:250px";
        var opts = Object.keys(measures).map(function(k) {
          return '<label style="display:block;cursor:pointer"><input type="radio" name="{{ this.uid }}" value="' + k + '"' +
                 (k === current ? " checked" : "") + '> ' + measures[k] + '</label>';
        }).join("");
        var cs = '<option value="">All of sub-Saharan Africa</option>' + Object.keys(bounds).sort().map(function(c) {
          return '<option>' + c + '</option>'; }).join("");
        d.innerHTML = '<b>Show on hexagons</b>' + opts +
          '<div style="margin-top:6px"><b>Zoom to</b><br><select style="width:100%">' + cs + '</select></div>' +
          '<div style="margin-top:6px"><b>Opacity</b><input type="range" min="0.1" max="1" step="0.05" value="0.75" style="width:100%"></div>' +
          '<div id="{{ this.uid }}-legend" style="margin-top:6px"></div>';
        L.DomEvent.disableClickPropagation(d); L.DomEvent.disableScrollPropagation(d);
        d.querySelectorAll("input[type=radio]").forEach(function(r) {
          r.addEventListener("change", function() { current = this.value; restyle(); }); });
        d.querySelector("select").addEventListener("change", function() {
          var b = bounds[this.value] || {{ this.all_bounds }}; map.fitBounds(b); });
        d.querySelector("input[type=range]").addEventListener("input", function() {
          opacity = parseFloat(this.value); restyle(); });
        return d;
      };
      ctl.addTo(map);
      restyle();
    })();
    {% endmacro %}
    """)

    def __init__(self, m, layer, hx, measures, default):
        super().__init__()
        self.uid = self.get_name()
        self.map_name, self.layer_name = m.get_name(), layer.get_name()
        self.default = default
        self.measures = json.dumps(measures)
        legends = {k: _legend_html(k) for k in measures if k in MEASURES}
        legends["profile"] = _profile_legend()
        legends["hotspot"] = ("<b>DBSCAN hotspots</b><div><span style='display:inline-block;width:11px;height:11px;"
                              "background:#b2182b;margin-right:5px'></span>Inside an 'all three high' hotspot</div>")
        self.legends = json.dumps(legends)
        b = {}
        for c, g in hx.groupby("country"):
            x0, y0, x1, y1 = g.total_bounds
            b[c] = [[y0, x0], [y1, x1]]
        self.bounds = json.dumps(b)
        x0, y0, x1, y1 = hx.total_bounds
        self.all_bounds = json.dumps([[y0, x0], [y1, x1]])


def explorer_map(height=680):
    hx = hex_features()
    m = folium.Map(location=[3, 18], zoom_start=4, tiles=None, control_scale=True, height=height)
    folium.TileLayer("Esri.WorldGrayCanvas", name="Light grey basemap").add_to(m)
    folium.TileLayer("OpenStreetMap", name="Street map", show=False).add_to(m)
    folium.TileLayer("Esri.WorldImagery", name="Satellite", show=False).add_to(m)

    # open raster surfaces (not DHS) as image overlays
    rb = json.load(open(PUB / "raster_bounds.json"))
    for key, label in [("malaria_2005", "Malaria surface 2005 (Malaria Atlas Project)"),
                       ("malaria_2020", "Malaria surface 2020 (Malaria Atlas Project)"),
                       ("rain_annual", "Typical annual rainfall 1981–2010 (CHIRPS)")]:
        png = f"raster_{key}.png" if key != "rain_annual" else "raster_rain_annual.png"
        folium.raster_layers.ImageOverlay(str(PUB / png), bounds=rb[key], name=label, opacity=0.8,
                                          show=False, zindex=2).add_to(m)

    cols = TOOLTIP_FIELDS + [c for c in hx.columns if c.startswith("c_")] + ["geometry"]
    gj = folium.GeoJson(
        hx[cols], name="DHS hexagons (pick the measure in the panel →)",
        style_function=lambda f: {"fillColor": f["properties"]["c_anemia_pct"], "fillOpacity": 0.75,
                                  "color": "#ffffff", "weight": 0.4},
        highlight_function=lambda f: {"weight": 2.5, "color": "#222222"},
        tooltip=folium.GeoJsonTooltip(fields=TOOLTIP_FIELDS, aliases=TOOLTIP_ALIASES, localize=True,
                                      sticky=True, style="font-size:12px"),
        zoom_on_click=False)
    gj.add_to(m)

    rg = regions(0.02)
    folium.GeoJson(rg[["region", "country", "geometry"]], name="Region borders (admin-1)",
                   style_function=lambda f: {"fill": False, "color": "#333333", "weight": 0.8},
                   tooltip=folium.GeoJsonTooltip(["region", "country"], aliases=["Region", "Country"]),
                   show=False).add_to(m)

    measures = {"anemia_pct": "Anemia", "od_pct": "Open defecation", "pfpr": "Malaria",
                "rain_3mo_z": "Rainfall anomaly", "rain_annual_mm": "Typical rainfall", "wealth": "Wealth",
                "profile": "Profile (k-means)", "hotspot": "Hotspots (DBSCAN)", "abs_err": "Model error"}
    m.add_child(MeasurePanel(m, gj, hx, measures, "anemia_pct"))
    folium.LayerControl(position="topleft", collapsed=True).add_to(m)
    Fullscreen(position="topleft").add_to(m)
    return m


def dual_map(left="od_pct", right="pfpr", height=520):
    """Two synced maps side by side, e.g. open defecation vs malaria."""
    from folium.plugins import DualMap
    hx = hex_features()
    m = DualMap(location=[5, 15], zoom_start=4, tiles="Esri.WorldGrayCanvas")
    for side, key in [(m.m1, left), (m.m2, right)]:
        folium.GeoJson(
            hx[["country", "n_clusters", key, f"c_{key}", "geometry"]],
            style_function=lambda f, k=key: {"fillColor": f["properties"][f"c_{k}"], "fillOpacity": 0.8,
                                             "color": "#fff", "weight": 0.3},
            tooltip=folium.GeoJsonTooltip(["country", "n_clusters", key],
                                          aliases=["Country", "DHS clusters", MEASURES[key][0]]),
        ).add_to(side)
        lg = MacroElement()
        lg._template = Template("""{% macro script(this, kwargs) %}
            var lg = L.control({position: "bottomleft"});
            lg.onAdd = function() { var d = L.DomUtil.create("div");
              d.style.cssText = "background:white;padding:6px 8px;border-radius:4px;font:12px sans-serif";
              d.innerHTML = """ + json.dumps(_legend_html(key)) + """; return d; };
            lg.addTo(""" + side.get_name() + """);
        {% endmacro %}""")
        side.add_child(lg)
    return m
