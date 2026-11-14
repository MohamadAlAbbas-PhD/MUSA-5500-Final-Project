"use strict";
/* Interactive atlas: reads exported, aggregated files from assets/ (no DHS microdata). */

const PROFILES = {
  "All three high": "#b2182b", "High anemia + malaria": "#7b3294", "High open defecation": "#bf812d",
  "High anemia": "#f4a582", "All three low": "#5aae61",
};
const PROFILE_TEXT = {
  "All three high": "Most children anemic, most households without a toilet, heavy malaria.",
  "High anemia + malaria": "Anemia tracks malaria here; most households do have a toilet.",
  "High open defecation": "Toilets are rare, but malaria is low and anemia closer to average.",
  "High anemia": "Anemia is common even though toilets are common and malaria is low.",
  "All three low": "The best-off places: lower anemia, toilets, little malaria.",
};
const MEASURES = {
  anemia_pct:     { label: "Child anemia", unit: "%", stops: ["#fee5d9", "#fcae91", "#fb6a4a", "#de2d26", "#a50f15"], min: 20, max: 95, desc: "Children aged 6–59 months with anemia" },
  od_pct:         { label: "Open defecation", unit: "%", stops: ["#ffffd4", "#fed98e", "#fe9929", "#d95f0e", "#993404"], min: 0, max: 100, desc: "Households with no toilet" },
  pfpr:           { label: "Malaria", unit: "%", stops: ["#f2f0f7", "#cbc9e2", "#9e9ac8", "#756bb1", "#54278f"], min: 0, max: 70, desc: "P. falciparum prevalence, age 2–10" },
  rain_3mo_z:     { label: "Rainfall anomaly", unit: " SD", stops: ["#8c510a", "#d8b365", "#f5f5f5", "#5ab4ac", "#01665e"], min: -2, max: 2, desc: "3 months before the survey vs. 1981–2010 (dry ← → wet)" },
  rain_annual_mm: { label: "Typical rainfall", unit: " mm", stops: ["#f7fbff", "#c6dbef", "#6baed6", "#2171b5", "#08306b"], min: 200, max: 2500, desc: "Mean annual rainfall 1981–2010" },
  wealth:         { label: "Wealth", unit: "", stops: ["#edf8e9", "#bae4b3", "#74c476", "#31a354", "#006d2c"], min: 1, max: 5, desc: "Average wealth quintile (1 poorest – 5 richest, within country)" },
  profile:        { label: "Profile (k-means)", categorical: true, desc: "Most common k-means profile in the hexagon" },
  hotspot:        { label: "Hotspots (DBSCAN)", unit: "%", stops: ["#fff5f0", "#fcbba1", "#fb6a4a", "#cb181d", "#67000d"], min: 0, max: 100, desc: "Share of the hexagon's clusters inside a DBSCAN hotspot" },
  abs_err:        { label: "Model error", unit: " pp", stops: ["#feedde", "#fdbe85", "#fd8d3c", "#e6550d", "#a63603"], min: 5, max: 30, desc: "Random forest's average miss (percentage points)" },
};
const AXES = { od_pct: "Open defecation (%)", anemia_pct: "Child anemia (%)", pfpr: "Malaria (%)", rain_3mo_z: "Rainfall anomaly (SD)",
  rain_annual_mm: "Typical rainfall (mm)", wealth: "Wealth quintile", mom_secondary_pct: "Mothers w/ secondary school (%)" };

const state = { measure: "anemia_pct", profile: null, brush: null, country: "", eps: 50, opacity: 0.8 };
let map, hexLayer, features = [], avg = {}, bounds = {}, overlays = {};

// ---------- helpers ----------
const $ = id => document.getElementById(id);
const fmt = (v, d = 0) => (v == null || Number.isNaN(v)) ? "–" : Number(v).toLocaleString(undefined, { maximumFractionDigits: d, minimumFractionDigits: d });
function hex2rgb(h) { const n = parseInt(h.slice(1), 16); return [n >> 16, (n >> 8) & 255, n & 255]; }
function ramp(stops, t) {
  t = Math.max(0, Math.min(1, t)); const p = t * (stops.length - 1), i = Math.min(Math.floor(p), stops.length - 2), f = p - i;
  const a = hex2rgb(stops[i]), b = hex2rgb(stops[i + 1]);
  return `rgb(${a.map((x, k) => Math.round(x + (b[k] - x) * f)).join(",")})`;
}
function valueOf(p, m) { return m === "hotspot" ? p[`hot_${state.eps}`] : p[m]; }
function colorOf(p, m = state.measure) {
  const c = MEASURES[m];
  if (c.categorical) return PROFILES[p.profile_name] || "#ccc";
  const v = valueOf(p, m);
  if (v == null) return "#cccccc";
  if (m === "hotspot" && p.profile1_pct === 0) return "#eeeeee";
  return ramp(c.stops, (v - c.min) / (c.max - c.min));
}
function parseCSV(text) {
  const rows = []; let row = [], cur = "", q = false;
  for (let i = 0; i < text.length; i++) {
    const ch = text[i];
    if (q) { if (ch === '"' && text[i + 1] === '"') { cur += '"'; i++; } else if (ch === '"') q = false; else cur += ch; }
    else if (ch === '"') q = true;
    else if (ch === ",") { row.push(cur); cur = ""; }
    else if (ch === "\n" || ch === "\r") { if (ch === "\r" && text[i + 1] === "\n") i++; row.push(cur); rows.push(row); row = []; cur = ""; }
    else cur += ch;
  }
  if (cur || row.length) { row.push(cur); rows.push(row); }
  const head = rows.shift();
  return rows.filter(r => r.length === head.length).map(r => Object.fromEntries(head.map((h, i) => [h, isNaN(+r[i]) || r[i] === "" ? r[i] : +r[i]])));
}
async function get(path, kind = "json") {
  const r = await fetch(path);
  if (!r.ok) throw new Error(`Could not load ${path} (HTTP ${r.status})`);
  return kind === "json" ? r.json() : r.text();
}

// ---------- map ----------
function visible(p) {
  if (state.profile && p.profile_name !== state.profile) return false;
  if (state.brush && !state.brush.has(p.hex)) return false;
  return true;
}
function styleFn(f) {
  const p = f.properties, show = visible(p);
  return { fillColor: colorOf(p), fillOpacity: show ? state.opacity : 0, color: "#ffffff",
           weight: show ? 0.4 : 0, opacity: show ? 1 : 0 };
}
function restyle() { hexLayer.setStyle(styleFn); drawLegend(); drawScatter(); }

function drawLegend() {
  const m = state.measure, c = MEASURES[m];
  let html = `<b>${c.label}</b><div class="muted">${c.desc}${m === "hotspot" ? ` (radius ${state.eps} km)` : ""}</div>`;
  if (c.categorical) html += Object.entries(PROFILES).map(([n, col]) => `<div><span class="sw" style="background:${col}"></span>${n}</div>`).join("");
  else html += `<div class="ramp" style="background:linear-gradient(to right,${c.stops.join(",")})"></div>
    <div class="ends"><span>${c.min}${c.unit}</span><span>${c.max}${c.unit}</span></div>`;
  const n = features.filter(f => visible(f.properties)).length;
  html += `<div class="muted" style="margin-top:4px">${n.toLocaleString()} of ${features.length.toLocaleString()} hexagons shown</div>`;
  $("legend").innerHTML = html;
}

function showInfo(p) {
  const row = (lab, v, mx, col, a) => `<div class="row"><span>${lab}</span><div class="track">
      <span style="width:${Math.min(100, (v / mx) * 100)}%;background:${col}"></span><i style="left:${Math.min(100, (a / mx) * 100)}%" title="Average"></i></div>
      <b>${fmt(v)}</b></div>`;
  $("info").innerHTML = `<h4>${p.country}</h4>
    <div class="muted">${p.n_clusters} survey clusters · ${fmt(p.n_children)} children · surveys ${p.year_min}–${p.year_max}</div>
    <div style="margin:6px 0"><span class="sw" style="display:inline-block;width:10px;height:10px;background:${PROFILES[p.profile_name]};margin-right:5px"></span><b>${p.profile_name}</b></div>
    ${row("Anemia %", p.anemia_pct, 100, "#de2d26", avg.anemia_pct)}
    ${row("No toilet %", p.od_pct, 100, "#d95f0e", avg.od_pct)}
    ${row("Malaria %", p.pfpr, 100, "#756bb1", avg.pfpr)}
    ${row("Wealth (1–5)", p.wealth, 5, "#31a354", avg.wealth)}
    <div class="muted" style="margin-top:4px">Rain anomaly ${fmt(p.rain_3mo_z, 2)} SD · model predicted ${fmt(p.pred_anemia_pct)}% anemia.
    Black tick = average of all hexagons.</div>`;
}

function initMap(geo, rb, regions) {
  map = L.map("map", { zoomSnap: 0.5, minZoom: 3, scrollWheelZoom: false }).setView([3, 18], 4);
  // scroll-zoom only after clicking the map, so the page can scroll past it
  map.on("click", () => map.scrollWheelZoom.enable());
  map.on("mouseout", () => map.scrollWheelZoom.disable());
  L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}",
    { attribution: "Basemap © Esri", maxZoom: 12 }).addTo(map);
  overlays.lyrMalaria = L.imageOverlay("assets/raster_malaria_2020.png", rb.malaria_2020, { opacity: 0.8 });
  overlays.lyrMalaria05 = L.imageOverlay("assets/raster_malaria_2005.png", rb.malaria_2005, { opacity: 0.8 });
  overlays.lyrRain = L.imageOverlay("assets/raster_rain_annual.png", rb.rain_annual, { opacity: 0.8 });
  overlays.lyrRegions = L.geoJSON(regions, { style: { fill: false, color: "#444", weight: 0.7 }, interactive: false });
  hexLayer = L.geoJSON(geo, {
    style: styleFn,
    onEachFeature: (f, layer) => {
      const p = f.properties;
      layer.bindTooltip(() => {
        const m = state.measure, c = MEASURES[m];
        const v = c.categorical ? p.profile_name : `${fmt(valueOf(p, m), m === "rain_3mo_z" ? 2 : 0)}${c.unit}`;
        return `<b>${p.country}</b><br>${c.label}: ${v}`;
      }, { sticky: true });
      layer.on({ click: () => showInfo(p),
                 mouseover: e => e.target.setStyle({ weight: 2, color: "#222" }),
                 mouseout: e => hexLayer.resetStyle(e.target) });
    },
  }).addTo(map);
  for (const id of Object.keys(overlays)) {
    $(id).addEventListener("change", e => {
      if (e.target.checked) { overlays[id].addTo(map); if (id !== "lyrRegions") overlays[id].bringToBack(); }
      else map.removeLayer(overlays[id]);
      hexLayer.bringToFront();
    });
  }
}

// ---------- controls ----------
function initControls() {
  const box = $("measures");
  for (const [k, c] of Object.entries(MEASURES)) {
    const b = document.createElement("button");
    b.type = "button"; b.textContent = c.label; b.setAttribute("role", "radio");
    b.setAttribute("aria-checked", k === state.measure); b.dataset.k = k;
    b.addEventListener("click", () => setMeasure(k));
    box.append(b);
  }
  const sel = $("country");
  for (const c of Object.keys(bounds).filter(c => !c.startsWith("__")).sort()) sel.add(new Option(c, c));
  sel.addEventListener("change", () => {
    state.country = sel.value;
    map.flyToBounds(state.country ? bounds[state.country] : bounds.__all, { duration: 0.8 });
    drawScatter();
  });
  const chips = $("profileChips");
  for (const [n, col] of Object.entries(PROFILES)) {
    const b = document.createElement("button");
    b.type = "button"; b.className = "chip"; b.textContent = n; b.style.setProperty("--c", col);
    b.setAttribute("aria-pressed", "false"); b.dataset.p = n;
    b.addEventListener("click", () => setProfile(state.profile === n ? null : n));
    chips.append(b);
  }
  $("opacity").addEventListener("input", e => { state.opacity = +e.target.value; hexLayer.setStyle(styleFn); });
  for (const [id, def] of [["xVar", "od_pct"], ["yVar", "anemia_pct"]]) {
    const s = $(id);
    for (const [k, lab] of Object.entries(AXES)) s.add(new Option(lab, k, false, k === def));
    s.addEventListener("change", () => { state.brush = null; restyle(); });
  }
  $("clearBrush").addEventListener("click", () => { state.brush = null; restyle(); });
  $("eps").addEventListener("input", e => { state.eps = +e.target.value; drawHotspots(); if (state.measure === "hotspot") restyle(); });
  $("showHot").addEventListener("click", () => { setMeasure("hotspot"); setProfile(null); $("atlas").scrollIntoView({ behavior: "smooth" }); });
}
function setMeasure(k) {
  state.measure = k;
  document.querySelectorAll("#measures button").forEach(b => b.setAttribute("aria-checked", b.dataset.k === k));
  restyle();
}
function setProfile(n) {
  state.profile = n;
  document.querySelectorAll("#profileChips .chip").forEach(b => b.setAttribute("aria-pressed", b.dataset.p === n));
  document.querySelectorAll("#profileCards .card").forEach(b => b.setAttribute("aria-pressed", b.dataset.p === n));
  restyle();
}

// ---------- linked scatterplot with brushing ----------
let brushFinish = null;
for (const ev of ["pointerup", "mouseup"]) window.addEventListener(ev, e => { if (brushFinish) brushFinish(e); });
function drawScatter() {
  const W = 1200, H = 360, m = { l: 56, r: 16, t: 14, b: 44 };
  const xv = $("xVar").value, yv = $("yVar").value;
  const pts = features.map(f => f.properties).filter(p => p[xv] != null && p[yv] != null);
  const ext = k => { const v = pts.map(p => p[k]); return [Math.min(...v), Math.max(...v)]; };
  let [x0, x1] = ext(xv), [y0, y1] = ext(yv);
  if (xv.endsWith("_pct")) [x0, x1] = [0, 100];
  if (yv.endsWith("_pct")) [y0, y1] = [0, 100];
  const sx = v => m.l + (v - x0) / (x1 - x0 || 1) * (W - m.l - m.r);
  const sy = v => H - m.b - (v - y0) / (y1 - y0 || 1) * (H - m.t - m.b);
  const ticks = (a, b) => Array.from({ length: 6 }, (_, i) => a + (b - a) * i / 5);
  let s = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Scatterplot">`;
  s += `<g class="axis">`;
  for (const t of ticks(x0, x1)) s += `<line x1="${sx(t)}" x2="${sx(t)}" y1="${m.t}" y2="${H - m.b}" stroke-dasharray="2,3"/><text x="${sx(t)}" y="${H - m.b + 16}" text-anchor="middle">${fmt(t, Math.abs(x1 - x0) < 10 ? 1 : 0)}</text>`;
  for (const t of ticks(y0, y1)) s += `<line x1="${m.l}" x2="${W - m.r}" y1="${sy(t)}" y2="${sy(t)}" stroke-dasharray="2,3"/><text x="${m.l - 6}" y="${sy(t) + 4}" text-anchor="end">${fmt(t, Math.abs(y1 - y0) < 10 ? 1 : 0)}</text>`;
  s += `<text x="${(W + m.l) / 2}" y="${H - 6}" text-anchor="middle" style="font-size:13px">${AXES[xv]}</text>`;
  s += `<text transform="translate(14,${(H - m.b) / 2}) rotate(-90)" text-anchor="middle" style="font-size:13px">${AXES[yv]}</text></g>`;
  for (const p of pts) {
    const dim = !visible(p) || (state.country && p.country !== state.country);
    s += `<circle class="dot${dim ? " dim" : ""}" cx="${sx(p[xv]).toFixed(1)}" cy="${sy(p[yv]).toFixed(1)}" r="${(2 + Math.sqrt(p.n_clusters)).toFixed(1)}" fill="${colorOf(p)}"><title>${p.country}: ${AXES[xv]} ${fmt(p[xv], 1)}, ${AXES[yv]} ${fmt(p[yv], 1)}</title></circle>`;
  }
  s += `<rect id="brushRect" fill="rgba(123,45,38,.12)" stroke="#7b2d26" stroke-dasharray="4,3" width="0" height="0"/></svg>`;
  $("scatter").innerHTML = s;
  const shown = features.filter(f => visible(f.properties)).length;
  $("selCount").textContent = state.brush ? `${state.brush.size} hexagons selected` : `${shown.toLocaleString()} hexagons`;

  // brushing
  const svg = $("scatter").querySelector("svg"), rect = $("brushRect");
  const toSvg = e => { const r = svg.getBoundingClientRect(); return [(e.clientX - r.left) * W / r.width, (e.clientY - r.top) * H / r.height]; };
  let start = null;
  svg.addEventListener("pointerdown", e => { e.preventDefault(); start = toSvg(e); });
  svg.addEventListener("pointermove", e => {
    if (!start) return; const [x, y] = toSvg(e);
    rect.setAttribute("x", Math.min(x, start[0])); rect.setAttribute("y", Math.min(y, start[1]));
    rect.setAttribute("width", Math.abs(x - start[0])); rect.setAttribute("height", Math.abs(y - start[1]));
  });
  const finish = e => {
    if (!start) return; const [x, y] = toSvg(e), [a, b] = start; start = null;
    if (Math.abs(x - a) < 4 && Math.abs(y - b) < 4) { state.brush = null; restyle(); return; }
    const [xa, xb] = [Math.min(x, a), Math.max(x, a)], [ya, yb] = [Math.min(y, b), Math.max(y, b)];
    state.brush = new Set(pts.filter(p => { const px = sx(p[xv]), py = sy(p[yv]); return px >= xa && px <= xb && py >= ya && py <= yb; }).map(p => p.hex));
    restyle();
  };
  brushFinish = finish;          // one window-level listener (below) ends the drag wherever the mouse is released
}

// ---------- profiles ----------
function drawProfiles(prof, byCountry) {
  const bar = (v, col) => `<div class="b"><span style="width:${Math.min(v, 100)}%;background:${col}"></span></div>`;
  $("profileCards").innerHTML = prof.sort((a, b) => a.profile - b.profile).map(r => `
    <button type="button" class="card" data-p="${r.profile_name}" aria-pressed="false" style="--c:${PROFILES[r.profile_name]}">
      <h4>${r.profile_name}</h4>
      <div class="meta">${fmt(r.n_clusters)} clusters (${fmt(r.share_pct)}%) · ${fmt(r.n_children)} children</div>
      <p style="font-size:.88rem;margin:.4rem 0">${PROFILE_TEXT[r.profile_name]}</p>
      Anemia <b>${fmt(r.anemia_pct)}%</b>${bar(r.anemia_pct, "#de2d26")}
      No toilet <b>${fmt(r.od_pct)}%</b>${bar(r.od_pct, "#d95f0e")}
      Malaria <b>${fmt(r.pfpr)}%</b>${bar(r.pfpr, "#756bb1")}
      <div class="meta">Wealth ${fmt(r.wealth, 1)} · urban ${fmt(r.urban_pct)}%</div></button>`).join("");
  document.querySelectorAll("#profileCards .card").forEach(c => c.addEventListener("click", () => {
    setProfile(state.profile === c.dataset.p ? null : c.dataset.p);
    if (state.measure !== "profile") setMeasure("profile");
    $("atlas").scrollIntoView({ behavior: "smooth" });
  }));
  const rows = byCountry.sort((a, b) => b["All three high"] - a["All three high"]);
  $("countryBars").innerHTML = rows.map(r => `<div class="cbrow"><span>${r.country}</span><div class="stack">${
    Object.keys(PROFILES).map(n => `<span style="width:${r[n]}%;background:${PROFILES[n]}" title="${r.country}: ${n} ${fmt(r[n])}%"></span>`).join("")
  }</div><span class="muted">${fmt(r["All three high"])}%</span></div>`).join("") +
  `<div class="muted" style="margin-top:6px">${Object.entries(PROFILES).map(([n, c]) => `<span class="sw" style="display:inline-block;width:10px;height:10px;background:${c};margin:0 4px 0 10px"></span>${n}`).join("")}</div>`;
}

// ---------- hotspots ----------
let sens = [], hotTable = [];
function drawHotspots() {
  $("epsLabel").textContent = `${state.eps} km`;
  const s = sens.find(r => r.eps_km === state.eps);
  if (s) $("epsStats").textContent = `${s.n_hotspots} hotspots · ${fmt(s.clusters_in_hotspots)} clusters (${fmt(s.share_pct)}% of "all three high")`;
  $("hotTable").innerHTML = state.eps === 50
    ? `<tr><th>Hotspot</th><th>Clusters</th><th>Countries</th><th>Anemia %</th><th>No toilet %</th><th>Malaria %</th></tr>` +
      hotTable.map(r => `<tr><td>${r.hotspot}</td><td>${fmt(r.n_clusters)}</td><td>${r.countries}</td><td>${fmt(r.anemia_pct)}</td><td>${fmt(r.od_pct)}</td><td>${fmt(r.pfpr)}</td></tr>`).join("")
    : `<tr><td class="muted">The hotspot-by-hotspot table is shown for the 50 km radius used in the analysis. Move the slider back to 50 km to see it.</td></tr>`;
}

// ---------- start ----------
(async function main() {
  try {
    const [geo, rb, regions, summary, profTxt, bcTxt, sensTxt, hsTxt] = await Promise.all([
      get("assets/hexes.geojson"), get("assets/raster_bounds.json"), get("assets/regions.geojson"),
      get("assets/sample_summary.json"), get("assets/kmeans_profiles.csv", "text"),
      get("assets/profiles_by_country.csv", "text"), get("assets/dbscan_sensitivity.csv", "text"),
      get("assets/dbscan_summary.csv", "text")]);
    features = geo.features;
    for (const k of ["anemia_pct", "od_pct", "pfpr", "wealth"]) {
      const v = features.map(f => f.properties[k]).filter(x => x != null); avg[k] = v.reduce((a, b) => a + b, 0) / v.length;
    }
    const all = L.geoJSON(geo).getBounds(); bounds.__all = all;
    for (const f of features) {
      const c = f.properties.country, b = L.geoJSON(f).getBounds();
      bounds[c] = bounds[c] ? bounds[c].extend(b) : b;
    }
    $("stats").innerHTML = [
      [summary.children.toLocaleString(), "children tested for anemia"],
      [summary.clusters.toLocaleString(), "survey clusters"],
      [summary.countries, `countries · ${summary.surveys} surveys`],
      [`${summary.year_min}–${summary.year_max}`, "survey years"],
      [`${Math.round(summary.anemia_pct)}%`, "of children anemic (average cluster)"],
    ].map(([b, s]) => `<div class="stat"><b>${b}</b><span>${s}</span></div>`).join("");
    initMap(geo, rb, regions);
    initControls();
    sens = parseCSV(sensTxt); hotTable = parseCSV(hsTxt);
    drawProfiles(parseCSV(profTxt), parseCSV(bcTxt));
    drawHotspots();
    restyle();
  } catch (err) {
    const e = $("error"); e.hidden = false;
    e.textContent = `${err.message}. If you opened this file directly, preview it through http://localhost:8000 instead of file://.`;
    $("stats").textContent = "The data could not be loaded.";
    console.error(err);
  }
})();
