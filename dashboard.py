"""
Builds the single-file POC (Oferta de Capacidade) results dashboard from
data/poc_results.parquet.

Usage: python dashboard.py [output_path]  (default: docs/index.html)
"""
import base64
import gzip
import json
import sys
import datetime as dt
from pathlib import Path

import pandas as pd

HERE = Path(__file__).parent
PARQUET_PATH = HERE / "data" / "poc_results.parquet"
DEFAULT_OUT = HERE / "docs" / "index.html"
# Same Degular font file used by ons-dashboard, embedded the same way, so the
# two sites in the GasBrazil.com family actually render with the real
# typeface instead of POC silently falling back to the OS default because no
# @font-face for "Degular" was ever registered on this page.
FONT_PATH = HERE / "fonts" / "Degular.ttf"

# Price in the source data is R$/MMBtu. 28.8081 is the MMBtu-per-1000m3 factor
# implied by the dataset's PCR (poder calorifico de referencia) convention --
# dividing by it converts R$/MMBtu -> R$/m3.
MMBTU_PER_M3 = 28.8081

COLUMNS = [
    "Transporter (TSO)", "codigoProcesso", "Trade Date", "Flow Date Start", "Flow Date End",
    "Flow Days", "Trade Timing", "Transaction Type", "Delivery Point", "Service Type",
    "Price", "R$/m3", "Avg Process Price", "Volume Accepted", "Total Value",
    "Volume Offered", "Total Volume",
]

# Internal column key -> display label shown in the table header / CSV export.
# Keys not listed here are displayed as-is.
DISPLAY_NAMES = {
    "Transporter (TSO)": "Pipeline",
    "Price": "Price (R$/MMBtu)",
    "Avg Process Price": "Avg Process Price (R$/MMBtu)",
    "R$/m3": "R$/m³",
}

DATE_COLS = {"Trade Date", "Flow Date Start", "Flow Date End"}


def load_payload():
    df = pd.read_parquet(PARQUET_PATH)
    df["R$/m3"] = (df["Price"] / MMBTU_PER_M3).round(2)
    df = df[COLUMNS].copy()
    for c in DATE_COLS:
        df[c] = df[c].dt.strftime("%Y-%m-%d").where(df[c].notna(), None)
    # Normalize every remaining missing value (NaN/NaT/pd.NA) to None so json.dumps
    # never has to serialize a bare NaN (invalid JSON) for numeric or string columns.
    df = df.astype(object).where(pd.notna(df), None)
    records = df.to_dict(orient="records")

    generated = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    return {
        "generated": generated,
        "columns": COLUMNS,
        "displayNames": DISPLAY_NAMES,
        "rows": records,
    }


def encode_payload(payload):
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    compressed = gzip.compress(raw, mtime=0)
    return base64.b64encode(compressed).decode("ascii")


TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>POC Results Dashboard</title>
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'%3E%3Crect width='16' height='16' rx='3' fill='%2303183D'/%3E%3Cpath d='M3 11.5 6 7l3 2.5L13 4' stroke='white' stroke-width='1.6' fill='none' stroke-linecap='round' stroke-linejoin='round'/%3E%3C/svg%3E">
<style>
__FONT_FACE__
:root {
  /* Palette matched directly to ons-dashboard's tokens (--plane/--surface-1/
     --grid/--axis/--text-1/--text-2/--muted/--accent/--wash there) so the two
     GasBrazil.com dashboards read as one visual family, not just a shared
     accent color. --border/--border-strong split mirrors ons-dashboard's
     --grid (subtle dividers) vs --axis (control borders). */
  --bg: #f4f4f1; --panel: #fcfcfb; --border: #e1e0d9; --border-strong: #c3c2b7;
  --text: #0b0b0b; --muted: #898781; --muted2: #52514e;
  --accent: #03183D; --accent-soft: rgba(3,24,61,.08); --pos: #03183D; --neg: #b3441e;
  --shadow: none;
  --font: "Degular", system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
}
[data-theme="dark"] {
  --bg: #0d0d0d; --panel: #1a1a19; --border: #2c2c2a; --border-strong: #383835;
  --text: #ffffff; --muted: #898781; --muted2: #c3c2b7;
  --accent: #4a78c2; --accent-soft: rgba(74,120,194,.16); --pos: #4a78c2; --neg: #e08a5f;
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--text); font-family: var(--font); font-size: 14px; }
/* Same outer shell as ons-dashboard: a centered 1440px column with identical
   padding, in normal document flow -- that page scrolls normally too; only
   its own data tables cap their height and scroll internally (see the
   .table-wrap comment below). */
.wrap { max-width: 1440px; margin: 0 auto; padding: 20px 20px 64px; }
header { display: flex; flex-wrap: wrap; gap: 12px; align-items: baseline; justify-content: space-between; margin-bottom: 14px; }
h1 { font-size: 25px; margin: 0; letter-spacing: -.01em; }
.subtitle { color: var(--muted2); font-size: 13px; }
.header-right { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.header-links { display: flex; gap: 8px; flex-wrap: wrap; }
.sources { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; margin: 0 0 14px; }
.sources-label { font-size: 11px; text-transform: uppercase; letter-spacing: .06em; color: var(--muted); font-weight: 600; margin-right: 2px; }
.pill { font-size: 11.5px; color: var(--muted2); text-decoration: none; border: 1px solid var(--border); border-radius: 999px; padding: 3px 10px; white-space: nowrap; }
.pill:hover { background: var(--accent-soft); color: var(--text); border-color: var(--border-strong); }
.navlink { font-size: 11.5px; color: var(--accent); text-decoration: none; font-weight: 600; border: 1px solid var(--accent); border-radius: 999px; padding: 3px 10px; white-space: nowrap; }
.navlink:hover { background: var(--accent); color: #fff; }
#theme-toggle { display: inline-flex; align-items: center; justify-content: center; background: var(--panel); border: 1px solid var(--border-strong); border-radius: 6px; padding: 5px 9px; line-height: 0; cursor: pointer; color: var(--text); }
#theme-toggle:hover { background: var(--accent-soft); }
#theme-toggle svg { width: 16px; height: 16px; display: block; }
.tso-row { display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 14px; }
.tso-chip { background: var(--panel); border: 1px solid var(--border); border-radius: 999px; padding: 4px 12px; font-size: 12px; box-shadow: var(--shadow); white-space: nowrap; }
.tso-chip.empty { color: var(--muted); }
.tso-chip b { font-weight: 700; }
.tso-chip .muted { color: var(--muted); }
.quick-filters { display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 14px; }
.qf-btn { background: var(--panel); border: 1px solid var(--border); border-radius: 999px; padding: 4px 12px; font-size: 12px; cursor: pointer; color: var(--text); font-family: var(--font); }
.qf-btn:hover { background: var(--accent-soft); }
.qf-btn.active { background: var(--accent); color: #fff; border-color: var(--accent); }
.toolbar { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; margin-bottom: 14px; }
.toolbar select, .toolbar input { background: var(--panel); border: 1px solid var(--border-strong); border-radius: 6px; padding: 5px 10px; color: var(--text); font-size: 12.5px; font-family: var(--font); }
.toolbar select:hover { background: var(--accent-soft); }
.toolbar button { background: var(--panel); color: var(--text); border: 1px solid var(--border-strong); border-radius: 6px; padding: 5px 10px; font-size: 12.5px; cursor: pointer; font-family: var(--font); }
.toolbar button:hover { background: var(--accent-soft); }
.toolbar button.secondary { background: var(--panel); color: var(--text); border: 1px solid var(--border-strong); }
.count { color: var(--muted); font-size: 12px; margin-left: auto; }
/* Capped-height, internally-scrolling table -- the same pattern ons-dashboard
   uses for its own data tables (.scroll / .entlist there: max-height +
   overflow, sticky header), just taller since here the table is the page's
   primary content rather than a small secondary widget. */
.table-wrap { background: var(--panel); border: 1px solid var(--border); border-radius: 10px; overflow: auto; box-shadow: var(--shadow); max-height: 65vh; }
table { border-collapse: collapse; width: auto; min-width: 100%; font-size: 12.5px; white-space: nowrap; table-layout: auto; }
th, td { padding: 6px 10px; text-align: left; border-bottom: 1px solid var(--border); }
th { position: sticky; top: 0; background: var(--panel); cursor: pointer; user-select: none; color: var(--muted2); font-weight: 600; z-index: 2; position: relative; }
th:hover { background: var(--accent-soft); }
th.dragging { opacity: .4; }
th.drag-over { box-shadow: inset 2px 0 0 var(--accent); }
th .head-inner { display: inline-flex; align-items: center; gap: 3px; }
th .arrow { opacity: .4; }
th .filter-icon { opacity: .45; font-size: 10px; padding: 0 2px; }
th .filter-icon:hover, th .filter-icon.active { opacity: 1; color: var(--accent); }
th .resizer { position: absolute; right: 0; top: 0; width: 6px; height: 100%; cursor: col-resize; z-index: 3; }
th .resizer:hover, th .resizer.active { background: var(--accent); opacity: .5; }
.truncate { overflow: hidden; text-overflow: ellipsis; }
tbody tr:hover { background: var(--accent-soft); }
.num { text-align: right; font-variant-numeric: tabular-nums; }
footer { margin-top: 22px; color: var(--muted); font-size: 11.5px; line-height: 1.7; }
footer a { color: var(--accent); }
.filter-menu { position: fixed; background: var(--panel); border: 1px solid var(--border); border-radius: 8px; box-shadow: 0 6px 20px rgba(0,0,0,.16); padding: 8px; z-index: 50; min-width: 190px; max-width: 260px; font-weight: 400; color: var(--text); font-size: 12.5px; }
.filter-menu .fm-list { max-height: 220px; overflow: auto; margin: 4px 0; }
.filter-menu .fm-item { display: flex; align-items: center; gap: 6px; padding: 3px 2px; cursor: pointer; }
.filter-menu .fm-item input { margin: 0; }
.filter-menu .fm-row { display: flex; justify-content: space-between; gap: 6px; }
.filter-menu .fm-row.actions { margin-top: 6px; padding-top: 6px; border-top: 1px solid var(--border); }
.filter-menu button { font-size: 11.5px; padding: 4px 10px; border-radius: 6px; cursor: pointer; }
.filter-menu button.link { background: none; border: none; color: var(--accent); padding: 2px 0; }
.filter-menu button.primary { background: var(--accent); color: #fff; border: none; }
.filter-menu button.secondary { background: var(--panel); color: var(--text); border: 1px solid var(--border); }
.filter-menu label.fm-date { display: block; font-size: 11px; color: var(--muted); margin: 6px 0 3px; }
.filter-menu input[type="date"] { width: 100%; }
.filter-menu input[type="text"].fm-search { width: 100%; box-sizing: border-box; padding: 4px 6px; border: 1px solid var(--border); border-radius: 6px; background: var(--bg); color: var(--text); font-family: var(--font); font-size: 12px; margin-bottom: 6px; }
</style>
</head>
<body>
<div class="wrap">
<header>
  <div>
    <h1>POC Results Dashboard</h1>
    <div class="subtitle" id="subtitle">Last refreshed &mdash;</div>
  </div>
  <div class="header-right">
    <div class="header-links">
      <a class="navlink" id="link-home" href="https://gasbrazil.com">&larr; GasBrazil.com</a>
      <a class="navlink" id="link-ons" href="https://ons.gasbrazil.com">ONS Balances Dashboard &rarr;</a>
    </div>
    <button id="theme-toggle" title="Toggle theme" aria-label="Toggle theme"></button>
  </div>
</header>
<div class="sources">
  <span class="sources-label">Data source</span>
  <a class="pill" href="https://www.ofertadecapacidade.com.br/PEG/resultado" target="_blank" rel="noopener">Portal de Oferta de Capacidade</a>
</div>
<div class="tso-row" id="tso-row"></div>
<div class="quick-filters" id="quick-filters"></div>
<div class="toolbar">
  <select id="f-timing"><option value="">All trade timing</option></select>
  <input id="f-search" type="search" placeholder="Search process / delivery point&hellip;">
  <button class="secondary" id="btn-reset">Reset filters</button>
  <button class="secondary" id="btn-refresh" title="Reload the latest published build. Data itself refreshes automatically every 6 hours; this does not trigger a new pull.">&#8635; Reload latest</button>
  <button class="secondary" id="btn-columns" title="Show or hide columns">Columns</button>
  <button id="btn-csv">Download CSV</button>
  <span class="count" id="row-count"></span>
</div>
<div class="table-wrap">
  <table id="data-table">
    <thead><tr id="thead-row"></tr></thead>
    <tbody id="tbody"></tbody>
  </table>
</div>
<footer>
  &copy; <span id="year"></span> GasBrazil.com &middot; Data: Portal de Oferta de Capacidade (public API) &middot; Contact: <a href="mailto:eb@gasbrazil.com">eb@gasbrazil.com</a>
</footer>
</div>
<script>
const PAYLOAD_B64 = "__PAYLOAD__";

function b64ToBytes(b64) {
  const bin = atob(b64);
  const bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  return bytes;
}

async function inflate(bytes) {
  const ds = new DecompressionStream("gzip");
  const stream = new Blob([bytes]).stream().pipeThrough(ds);
  const buf = await new Response(stream).arrayBuffer();
  return new TextDecoder().decode(buf);
}

const NUMERIC_COLS = new Set(["Flow Days", "Price", "R$/m3", "Avg Process Price", "Volume Accepted", "Total Value", "Volume Offered", "Total Volume"]);
const DEFAULT_COL_WIDTH = { "Service Type": 220 };
// Columns hidden by default so the table fits most screens without horizontal
// scrolling. Users can re-enable any of these (or hide more) from the Columns
// menu; the choice is remembered in localStorage.
const DEFAULT_HIDDEN_COLS = ["codigoProcesso", "Flow Days", "Service Type", "Avg Process Price", "Total Value", "Volume Offered", "Total Volume"];
const COL_PREFS_KEY = "pocDashboard.columnPrefs.v1";
// Every column gets an Excel-style header filter menu: a date-range picker for
// the date columns, a searchable checkbox list for everything else.
const DATE_FILTER_COLS = new Set(["Trade Date", "Flow Date Start", "Flow Date End"]);

// Quick-filter chips above the toolbar. "set" writes columnFilters[col] to a
// Set of allowed values (same shape the header checkbox menu uses); "days"
// writes a {from, to} range ending today (same shape the date-range menu
// uses). Clicking an already-active chip clears that column's filter.
const QUICK_FILTERS = [
  { key: "last7", label: "Last 7 Days", col: "Trade Date", type: "days", days: 7 },
  { key: "last30", label: "Last 30 Days", col: "Trade Date", type: "days", days: 30 },
  { key: "gus-residual", label: "GUS + Residual Balancing", col: "Transaction Type", type: "set", values: ["GUS Acquisition", "Residual Balancing"] },
  { key: "tso-TAG", label: "TAG", col: "Transporter (TSO)", type: "set", values: ["TAG"] },
  { key: "tso-NTS", label: "NTS", col: "Transporter (TSO)", type: "set", values: ["NTS"] },
  { key: "tso-TBG", label: "TBG", col: "Transporter (TSO)", type: "set", values: ["TBG"] },
];

function fmtNum(v, maxFrac) {
  if (v === null || v === undefined || v === "") return "";
  return Number(v).toLocaleString("en-US", { maximumFractionDigits: maxFrac === undefined ? 2 : maxFrac });
}

function label(col) {
  return (DATA.displayNames && DATA.displayNames[col]) || col;
}

function visibleColumnList() {
  return columnOrder.filter(c => !hiddenCols.has(c));
}

function saveColumnPrefs() {
  try {
    localStorage.setItem(COL_PREFS_KEY, JSON.stringify({
      hidden: [...hiddenCols],
      order: columnOrder,
      widths: columnWidths,
    }));
  } catch (e) { /* storage unavailable (private browsing, etc.) -- ignore */ }
}

function loadColumnPrefs() {
  try {
    const raw = localStorage.getItem(COL_PREFS_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch (e) {
    return null;
  }
}

// This same built HTML file is published to three places at once (custom
// domain, the caissonpoint GitHub Pages URL, and the gasbrazil.github.io
// hub mirror), so the "back to GasBrazil.com" / "other dashboard" links
// can't be baked in at build time -- they're resolved from location.hostname
// at view time so each copy links to its own equivalent siblings.
const SITE_LINKS = {
  home: {
    custom: "https://gasbrazil.com",
    caissonpoint: "https://caissonpoint.github.io/gasbrazil-com/",
    hub: "https://gasbrazil.github.io/",
  },
  ons: {
    custom: "https://ons.gasbrazil.com",
    caissonpoint: "https://caissonpoint.github.io/ons-dashboard/",
    hub: "https://gasbrazil.github.io/ons/",
  },
};

function siteFlavor() {
  const h = location.hostname;
  if (h === "gasbrazil.github.io") return "hub";
  if (h === "caissonpoint.github.io") return "caissonpoint";
  return "custom"; // gasbrazil.com / *.gasbrazil.com -- also the safe default for local/unknown hosts
}

function initCrossLinks() {
  const flavor = siteFlavor();
  document.getElementById("link-home").href = SITE_LINKS.home[flavor];
  document.getElementById("link-ons").href = SITE_LINKS.ons[flavor];
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

let DATA = null;
let sortCol = "Trade Date";
let sortDir = -1; // 1 = ascending, -1 = descending, 0 = unsorted (third click on a header)
let filtered = [];
let columnWidths = Object.assign({}, DEFAULT_COL_WIDTH);
let columnOrder = [];
let hiddenCols = new Set(DEFAULT_HIDDEN_COLS);
// columnFilters["Trade Date"] = {from, to}; columnFilters[otherCol] = Set of allowed values.
let columnFilters = {};
let draggedCol = null;

function populateSelect(sel, values) {
  const uniq = [...new Set(values.filter(v => v !== null && v !== undefined && v !== ""))].sort();
  for (const v of uniq) {
    const opt = document.createElement("option");
    opt.value = v; opt.textContent = v;
    sel.appendChild(opt);
  }
}

function applyColWidth(el, px) {
  el.style.width = px + "px";
  el.style.maxWidth = px + "px";
  el.classList.add("truncate");
}

// Column widths must survive renderTable() rebuilding tbody's innerHTML on every
// filter/sort/keystroke -- columnWidths is the persistent source of truth; both
// header cells (rebuilt on reorder) and body cells (rebuilt constantly) read from it.
function makeResizable() {
  const ths = document.querySelectorAll("#thead-row th");
  const visCols = visibleColumnList();
  ths.forEach((th, idx) => {
    const col = visCols[idx];
    const resizer = document.createElement("div");
    resizer.className = "resizer";
    th.appendChild(resizer);
    resizer.addEventListener("mousedown", e => {
      e.preventDefault();
      e.stopPropagation();
      const startX = e.pageX;
      const startWidth = th.getBoundingClientRect().width;
      resizer.classList.add("active");
      function onMove(e2) {
        const newWidth = Math.max(44, startWidth + (e2.pageX - startX));
        columnWidths[col] = newWidth;
        applyColWidth(th, newWidth);
        document.querySelectorAll(`#tbody tr > td:nth-child(${idx + 1})`).forEach(td => applyColWidth(td, newWidth));
      }
      function onUp() {
        resizer.classList.remove("active");
        document.removeEventListener("mousemove", onMove);
        document.removeEventListener("mouseup", onUp);
        saveColumnPrefs();
      }
      document.addEventListener("mousemove", onMove);
      document.addEventListener("mouseup", onUp);
    });
  });
}

function closeFilterMenus() {
  document.querySelectorAll(".filter-menu").forEach(m => m.remove());
}

function updateFilterIcons() {
  const visCols = visibleColumnList();
  document.querySelectorAll("#thead-row th").forEach((th, idx) => {
    const col = visCols[idx];
    const icon = th.querySelector(".filter-icon");
    if (icon) icon.classList.toggle("active", !!columnFilters[col]);
  });
}

function openFilterMenu(col, anchorEl) {
  const alreadyOpen = document.querySelector(".filter-menu");
  closeFilterMenus();
  if (alreadyOpen && alreadyOpen.dataset.col === col) return;

  const menu = document.createElement("div");
  menu.className = "filter-menu";
  menu.dataset.col = col;
  const rect = anchorEl.getBoundingClientRect();
  menu.style.left = Math.min(rect.left, window.innerWidth - 270) + "px";
  menu.style.top = (rect.bottom + 4) + "px";

  if (DATE_FILTER_COLS.has(col)) {
    const cur = columnFilters[col] || {};
    menu.innerHTML = `
      <label class="fm-date">From</label>
      <input type="date" class="fm-from" value="${cur.from || ""}">
      <label class="fm-date">To</label>
      <input type="date" class="fm-to" value="${cur.to || ""}">
      <div class="fm-row actions">
        <button class="secondary fm-clear">Clear</button>
        <button class="primary fm-apply">Apply</button>
      </div>`;
    menu.querySelector(".fm-apply").addEventListener("click", () => {
      const from = menu.querySelector(".fm-from").value;
      const to = menu.querySelector(".fm-to").value;
      if (from || to) columnFilters[col] = { from, to }; else delete columnFilters[col];
      closeFilterMenus();
      updateFilterIcons();
      render();
    });
    menu.querySelector(".fm-clear").addEventListener("click", () => {
      delete columnFilters[col];
      closeFilterMenus();
      updateFilterIcons();
      render();
    });
  } else {
    // Raw (untyped) unique values, sorted numerically for numeric columns and
    // lexicographically otherwise. Checkbox `value` attributes are always
    // strings, so filter Sets are stored/compared as strings via String(v) --
    // that's what lets a numeric column's active Set match r[col] (a number).
    const rawValues = [...new Set(DATA.rows.map(r => r[col]).filter(v => v !== null && v !== undefined && v !== ""))];
    if (NUMERIC_COLS.has(col)) rawValues.sort((a, b) => a - b); else rawValues.sort();
    const active = columnFilters[col];
    const itemsHtml = rawValues.map(v => {
      const vs = String(v);
      const checked = !active || active.has(vs) ? "checked" : "";
      const displayVal = NUMERIC_COLS.has(col) ? fmtNum(v) : escapeHtml(vs);
      return `<label class="fm-item"><input type="checkbox" value="${escapeHtml(vs)}" ${checked}> ${displayVal}</label>`;
    }).join("");
    menu.innerHTML = `
      <input type="text" class="fm-search" placeholder="Search&hellip;">
      <div class="fm-row">
        <button class="link fm-none">Clear</button>
        <button class="link fm-all">Select all</button>
      </div>
      <div class="fm-list">${itemsHtml}</div>
      <div class="fm-row actions">
        <span></span>
        <button class="primary fm-apply">Apply</button>
      </div>`;
    menu.querySelector(".fm-search").addEventListener("input", e => {
      const q = e.target.value.trim().toLowerCase();
      menu.querySelectorAll(".fm-item").forEach(item => {
        item.style.display = item.textContent.trim().toLowerCase().includes(q) ? "" : "none";
      });
    });
    // Select all / Clear act only on the currently visible (searched) rows.
    menu.querySelector(".fm-all").addEventListener("click", e => {
      e.preventDefault();
      menu.querySelectorAll(".fm-item").forEach(item => {
        if (item.style.display !== "none") item.querySelector("input").checked = true;
      });
    });
    menu.querySelector(".fm-none").addEventListener("click", e => {
      e.preventDefault();
      menu.querySelectorAll(".fm-item").forEach(item => {
        if (item.style.display !== "none") item.querySelector("input").checked = false;
      });
    });
    menu.querySelector(".fm-apply").addEventListener("click", () => {
      const checked = [...menu.querySelectorAll(".fm-list input:checked")].map(c => c.value);
      if (checked.length === 0 || checked.length === rawValues.length) delete columnFilters[col];
      else columnFilters[col] = new Set(checked);
      closeFilterMenus();
      updateFilterIcons();
      render();
    });
  }

  document.body.appendChild(menu);
  setTimeout(() => document.addEventListener("mousedown", onOutsideClick), 0);
  function onOutsideClick(e) {
    if (!menu.contains(e.target) && e.target !== anchorEl) {
      closeFilterMenus();
      document.removeEventListener("mousedown", onOutsideClick);
    }
  }
}

function openColumnMenu(anchorEl) {
  const already = document.querySelector('.filter-menu[data-col-menu]');
  closeFilterMenus();
  if (already) return;

  const menu = document.createElement("div");
  menu.className = "filter-menu";
  menu.dataset.colMenu = "1";
  const rect = anchorEl.getBoundingClientRect();
  menu.style.left = Math.min(rect.left, window.innerWidth - 270) + "px";
  menu.style.top = (rect.bottom + 4) + "px";

  const itemsHtml = columnOrder.map(col => {
    const checked = hiddenCols.has(col) ? "" : "checked";
    return `<label class="fm-item"><input type="checkbox" data-col="${escapeHtml(col)}" ${checked}> ${escapeHtml(label(col))}</label>`;
  }).join("");

  menu.innerHTML = `
    <div class="fm-list">${itemsHtml}</div>
    <div class="fm-row actions">
      <button class="link fm-default">Reset to default</button>
      <button class="link fm-all">Show all</button>
    </div>`;

  menu.querySelectorAll('input[type="checkbox"]').forEach(cb => {
    cb.addEventListener("change", () => {
      const col = cb.dataset.col;
      if (cb.checked) hiddenCols.delete(col); else hiddenCols.add(col);
      saveColumnPrefs();
      buildHeader();
      render();
    });
  });
  menu.querySelector(".fm-default").addEventListener("click", e => {
    e.preventDefault();
    hiddenCols = new Set(DEFAULT_HIDDEN_COLS);
    saveColumnPrefs();
    closeFilterMenus();
    buildHeader();
    render();
  });
  menu.querySelector(".fm-all").addEventListener("click", e => {
    e.preventDefault();
    hiddenCols = new Set();
    saveColumnPrefs();
    closeFilterMenus();
    buildHeader();
    render();
  });

  document.body.appendChild(menu);
  setTimeout(() => document.addEventListener("mousedown", onColMenuOutsideClick), 0);
  function onColMenuOutsideClick(e) {
    if (!menu.contains(e.target) && e.target !== anchorEl) {
      closeFilterMenus();
      document.removeEventListener("mousedown", onColMenuOutsideClick);
    }
  }
}

function buildHeader() {
  const tr = document.getElementById("thead-row");
  tr.innerHTML = "";
  const visCols = visibleColumnList();
  visCols.forEach((col, idx) => {
    const th = document.createElement("th");
    th.draggable = true;
    th.dataset.col = col;

    const inner = document.createElement("span");
    inner.className = "head-inner";
    const span = document.createElement("span");
    span.textContent = label(col);
    inner.appendChild(span);
    const icon = document.createElement("span");
    icon.className = "filter-icon";
    icon.textContent = "▾";
    icon.addEventListener("click", e => {
      e.stopPropagation();
      openFilterMenu(col, icon);
    });
    inner.appendChild(icon);
    const arrow = document.createElement("span");
    arrow.className = "arrow";
    inner.appendChild(arrow);
    th.appendChild(inner);

    th.addEventListener("click", e => {
      if (e.target.closest(".resizer") || e.target.closest(".filter-icon")) return;
      // Three-state cycle per column: ascending -> descending -> unsorted.
      // Clicking a different column always starts it at ascending.
      if (sortCol === col) {
        if (sortDir === 1) sortDir = -1;
        else if (sortDir === -1) { sortDir = 0; sortCol = null; }
        else { sortCol = col; sortDir = 1; }
      } else {
        sortCol = col; sortDir = 1;
      }
      render();
    });

    th.addEventListener("dragstart", e => {
      draggedCol = col;
      th.classList.add("dragging");
      e.dataTransfer.effectAllowed = "move";
    });
    th.addEventListener("dragend", () => {
      th.classList.remove("dragging");
      document.querySelectorAll("#thead-row th").forEach(x => x.classList.remove("drag-over"));
    });
    th.addEventListener("dragover", e => {
      e.preventDefault();
      if (col !== draggedCol) th.classList.add("drag-over");
    });
    th.addEventListener("dragleave", () => th.classList.remove("drag-over"));
    th.addEventListener("drop", e => {
      e.preventDefault();
      th.classList.remove("drag-over");
      if (!draggedCol || draggedCol === col) return;
      const fromIdx = columnOrder.indexOf(draggedCol);
      const toIdx = columnOrder.indexOf(col);
      columnOrder.splice(fromIdx, 1);
      columnOrder.splice(toIdx, 0, draggedCol);
      saveColumnPrefs();
      buildHeader();
      render();
    });

    tr.appendChild(th);
  });
  makeResizable();
  const ths = document.querySelectorAll("#thead-row th");
  visCols.forEach((col, idx) => {
    if (columnWidths[col]) applyColWidth(ths[idx], columnWidths[col]);
  });
  updateFilterIcons();
  updateArrows();
}

function applyFilters() {
  const timing = document.getElementById("f-timing").value;
  const search = document.getElementById("f-search").value.trim().toLowerCase();
  filtered = DATA.rows.filter(r => {
    if (timing && r["Trade Timing"] !== timing) return false;
    for (const col of DATA.columns) {
      const active = columnFilters[col];
      if (!active) continue;
      if (DATE_FILTER_COLS.has(col)) {
        if (active.from && (!r[col] || r[col] < active.from)) return false;
        if (active.to && (!r[col] || r[col] > active.to)) return false;
      } else if (!active.has(String(r[col]))) {
        return false;
      }
    }
    if (search) {
      const hay = ((r["codigoProcesso"] || "") + " " + (r["Delivery Point"] || "")).toLowerCase();
      if (!hay.includes(search)) return false;
    }
    return true;
  });
}

function sortRows() {
  if (!sortCol || sortDir === 0) return; // third click on a header clears sorting
  filtered.sort((a, b) => {
    let av = a[sortCol], bv = b[sortCol];
    if (av === null || av === undefined) av = "";
    if (bv === null || bv === undefined) bv = "";
    if (NUMERIC_COLS.has(sortCol)) { av = Number(av) || 0; bv = Number(bv) || 0; }
    if (av < bv) return -1 * sortDir;
    if (av > bv) return 1 * sortDir;
    return 0;
  });
}

function last7dRows() {
  const now = new Date();
  const cutoff = new Date(now.getTime() - 7 * 24 * 3600 * 1000);
  return DATA.rows.filter(r => {
    if (r["Price"] === null || r["Price"] === undefined || !r["Trade Date"]) return false;
    const d = new Date(r["Trade Date"]);
    return d >= cutoff && d <= now;
  });
}

function mean(nums) {
  const valid = nums.filter(n => n !== null && n !== undefined && !isNaN(n));
  if (!valid.length) return null;
  return valid.reduce((a, b) => a + b, 0) / valid.length;
}

// Shows every known pipeline, even ones with zero trades in the last 7 days --
// derived from the full dataset, not just the recent window, so a quiet pipeline
// doesn't just silently disappear from the row.
function renderTsoRow() {
  const allTsos = [...new Set(DATA.rows.map(r => r["Transporter (TSO)"]).filter(Boolean))].sort();
  const recent = last7dRows();
  const byTso = {};
  for (const r of recent) {
    const tso = r["Transporter (TSO)"];
    if (!tso) continue;
    (byTso[tso] = byTso[tso] || []).push(r);
  }
  const el = document.getElementById("tso-row");
  el.innerHTML = "";
  for (const tso of allTsos) {
    const rows = byTso[tso] || [];
    const avg = mean(rows.map(r => r["R$/m3"]));
    const chip = document.createElement("div");
    if (rows.length) {
      chip.className = "tso-chip";
      chip.innerHTML = `<b>${tso}</b> &middot; ${avg !== null ? avg.toFixed(2) : "—"} R$/m³ avg &middot; ${rows.length} trade${rows.length === 1 ? "" : "s"} <span class="muted">(7d)</span>`;
    } else {
      chip.className = "tso-chip empty";
      chip.innerHTML = `<b>${tso}</b> &middot; no trades <span class="muted">(7d)</span>`;
    }
    el.appendChild(chip);
  }
}

function isoDate(d) { return d.toISOString().slice(0, 10); }

function daysAgoRange(n) {
  const now = new Date();
  const from = new Date(now.getTime() - n * 24 * 3600 * 1000);
  return { from: isoDate(from), to: isoDate(now) };
}

function setsEqual(a, b) {
  if (a.size !== b.size) return false;
  for (const v of a) if (!b.has(v)) return false;
  return true;
}

function quickFilterActive(qf) {
  const active = columnFilters[qf.col];
  if (!active) return false;
  if (qf.type === "set") return active instanceof Set && setsEqual(active, new Set(qf.values));
  const range = daysAgoRange(qf.days);
  return active.from === range.from && active.to === range.to;
}

function toggleQuickFilter(qf) {
  if (quickFilterActive(qf)) {
    delete columnFilters[qf.col];
  } else if (qf.type === "set") {
    columnFilters[qf.col] = new Set(qf.values);
  } else {
    columnFilters[qf.col] = daysAgoRange(qf.days);
  }
  updateFilterIcons();
  render();
}

function buildQuickFilters() {
  const el = document.getElementById("quick-filters");
  el.innerHTML = "";
  for (const qf of QUICK_FILTERS) {
    const btn = document.createElement("button");
    btn.className = "qf-btn";
    btn.dataset.qf = qf.key;
    btn.textContent = qf.label;
    btn.addEventListener("click", () => toggleQuickFilter(qf));
    el.appendChild(btn);
  }
}

function updateQuickFilterButtons() {
  document.querySelectorAll(".qf-btn").forEach(btn => {
    const qf = QUICK_FILTERS.find(q => q.key === btn.dataset.qf);
    btn.classList.toggle("active", quickFilterActive(qf));
  });
}

function renderTable() {
  const tbody = document.getElementById("tbody");
  const frag = document.createDocumentFragment();
  const visCols = visibleColumnList();
  for (const row of filtered) {
    const tr = document.createElement("tr");
    for (const col of visCols) {
      const td = document.createElement("td");
      let v = row[col];
      if (v === null || v === undefined) v = "";
      if (NUMERIC_COLS.has(col)) {
        td.classList.add("num");
        td.textContent = v === "" ? "" : fmtNum(v);
      } else {
        td.textContent = v;
      }
      if (columnWidths[col]) applyColWidth(td, columnWidths[col]);
      tr.appendChild(td);
    }
    frag.appendChild(tr);
  }
  tbody.innerHTML = "";
  tbody.appendChild(frag);
  document.getElementById("row-count").textContent = `${filtered.length.toLocaleString("en-US")} of ${DATA.rows.length.toLocaleString("en-US")} rows`;
}

function updateArrows() {
  const ths = document.querySelectorAll("#thead-row th");
  const visCols = visibleColumnList();
  ths.forEach((th, idx) => {
    const arrow = th.querySelector(".arrow");
    if (!arrow) return;
    if (sortCol && visCols[idx] === sortCol) arrow.textContent = sortDir === 1 ? "↑" : "↓";
    else arrow.textContent = "";
  });
}

function render() {
  applyFilters();
  sortRows();
  renderTable();
  updateArrows();
  updateQuickFilterButtons();
}

function toCsvValue(v) {
  if (v === null || v === undefined) return "";
  const s = String(v);
  if (/[",\\n]/.test(s)) return '"' + s.replace(/"/g, '""') + '"';
  return s;
}

function downloadCsv() {
  const lines = [columnOrder.map(c => toCsvValue(label(c))).join(",")];
  for (const row of filtered) {
    lines.push(columnOrder.map(c => toCsvValue(row[c])).join(","));
  }
  const blob = new Blob([lines.join("\\n")], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "poc_results.csv";
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

// Same sun/moon icon markup as ons-dashboard (SUN_SVG/MOON_SVG there) --
// the icon shown is the mode a click switches TO, matching that dashboard's
// convention.
const SUN_SVG = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M6.34 17.66l-1.41 1.41M19.07 4.93l-1.41 1.41"/></svg>';
const MOON_SVG = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>';

function initTheme() {
  const btn = document.getElementById("theme-toggle");
  function setTheme(mode) {
    if (mode === "dark") { document.documentElement.setAttribute("data-theme", "dark"); btn.innerHTML = SUN_SVG; }
    else { document.documentElement.removeAttribute("data-theme"); btn.innerHTML = MOON_SVG; }
  }
  setTheme("light");
  btn.addEventListener("click", () => {
    const isDark = document.documentElement.getAttribute("data-theme") === "dark";
    setTheme(isDark ? "light" : "dark");
  });
}

async function init() {
  document.getElementById("year").textContent = new Date().getFullYear();
  const bytes = b64ToBytes(PAYLOAD_B64);
  const text = await inflate(bytes);
  DATA = JSON.parse(text);
  columnOrder = DATA.columns.slice();
  hiddenCols = new Set(DEFAULT_HIDDEN_COLS);
  const savedPrefs = loadColumnPrefs();
  if (savedPrefs) {
    const validCols = new Set(DATA.columns);
    if (Array.isArray(savedPrefs.order)) {
      const restoredOrder = savedPrefs.order.filter(c => validCols.has(c));
      for (const c of DATA.columns) if (!restoredOrder.includes(c)) restoredOrder.push(c);
      if (restoredOrder.length === DATA.columns.length) columnOrder = restoredOrder;
    }
    if (Array.isArray(savedPrefs.hidden)) hiddenCols = new Set(savedPrefs.hidden.filter(c => validCols.has(c)));
    if (savedPrefs.widths && typeof savedPrefs.widths === "object") columnWidths = Object.assign({}, DEFAULT_COL_WIDTH, savedPrefs.widths);
  }
  document.getElementById("subtitle").textContent = "Last refreshed " + DATA.generated;
  populateSelect(document.getElementById("f-timing"), DATA.rows.map(r => r["Trade Timing"]));
  buildHeader();
  renderTsoRow();
  buildQuickFilters();
  render();
  document.getElementById("f-timing").addEventListener("change", render);
  document.getElementById("f-search").addEventListener("input", render);
  document.getElementById("btn-reset").addEventListener("click", () => {
    document.getElementById("f-timing").value = "";
    document.getElementById("f-search").value = "";
    columnFilters = {};
    updateFilterIcons();
    render();
  });
  document.getElementById("btn-columns").addEventListener("click", e => {
    e.stopPropagation();
    openColumnMenu(e.currentTarget);
  });
  document.getElementById("btn-csv").addEventListener("click", downloadCsv);
  // Cache-busting reload -- fetches whatever the most recently published build
  // is (refreshed automatically every 6 hours by GitHub Actions). It does NOT
  // trigger a new pull from the source API: that can only happen server-side,
  // since the source has no CORS headers and a write-capable GitHub token
  // can't safely be embedded in a public static page.
  document.getElementById("btn-refresh").addEventListener("click", () => {
    location.href = location.pathname + "?refreshed=" + Date.now();
  });
  initTheme();
  initCrossLinks();
}
init();
</script>
</body>
</html>
"""


def write_dashboard(out_path=DEFAULT_OUT):
    payload = load_payload()
    b64 = encode_payload(payload)
    if FONT_PATH.exists():
        font_b64 = base64.b64encode(FONT_PATH.read_bytes()).decode("ascii")
        font_face = (
            "@font-face{font-family:'Degular';font-weight:400;font-style:normal;"
            "font-display:swap;src:url(data:font/ttf;base64," + font_b64 +
            ") format('truetype');}"
        )
    else:
        # Repo checkout missing fonts/Degular.ttf -- degrade to the system
        # fallback stack rather than shipping a broken @font-face rule.
        font_face = ""
    html = TEMPLATE.replace("__PAYLOAD__", b64).replace("__FONT_FACE__", font_face)
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    print(f"Wrote dashboard ({len(html):,} bytes, {len(payload['rows'])} rows) to {out_path}")


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_OUT
    write_dashboard(out)
