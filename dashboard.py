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
    n_processes = int(pd.read_parquet(PARQUET_PATH)["codigoProcesso"].nunique())
    trade_dates = pd.to_datetime(df["Trade Date"], errors="coerce").dropna()
    date_range = None
    if len(trade_dates):
        date_range = [trade_dates.min().strftime("%Y-%m-%d"), trade_dates.max().strftime("%Y-%m-%d")]

    return {
        "generated": generated,
        "columns": COLUMNS,
        "displayNames": DISPLAY_NAMES,
        "rows": records,
        "kpis": {
            "processes": n_processes,
            "rows": len(records),
            "dateRange": date_range,
        },
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
<style>
:root {
  --bg: #f7f8fa; --panel: #ffffff; --border: #e2e5ea; --text: #1a1d23; --muted: #6b7280;
  --accent: #1d6f5c; --accent-soft: #e6f2ef; --pos: #1d6f5c; --neg: #b3441e;
  --shadow: 0 1px 2px rgba(16,24,40,.04);
  --font: "Degular", "Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}
[data-theme="dark"] {
  --bg: #14161a; --panel: #1c1f24; --border: #2b2f36; --text: #ecedee; --muted: #9aa1ac;
  --accent: #4fbf9f; --accent-soft: #1c2e29; --pos: #4fbf9f; --neg: #e08a5f;
}
* { box-sizing: border-box; }
html, body { height: 100%; }
body { margin: 0; background: var(--bg); color: var(--text); font-family: var(--font); font-size: 14px; display: flex; flex-direction: column; overflow: hidden; }
header { padding: 12px 24px 10px; border-bottom: 1px solid var(--border); display: flex; align-items: baseline; justify-content: space-between; flex-wrap: wrap; gap: 8px; flex: none; }
h1 { font-size: 18px; margin: 0; font-weight: 700; }
.subtitle { color: var(--muted); font-size: 11.5px; margin-top: 2px; }
.sources { padding: 6px 24px; display: flex; gap: 10px; flex-wrap: wrap; border-bottom: 1px solid var(--border); flex: none; }
.pill { font-size: 11px; color: var(--muted); text-decoration: none; border: 1px solid var(--border); border-radius: 999px; padding: 2px 9px; }
.pill:hover { border-color: var(--accent); color: var(--accent); }
#theme-toggle { background: none; border: 1px solid var(--border); border-radius: 8px; width: 30px; height: 30px; cursor: pointer; font-size: 14px; color: var(--text); }
main { padding: 12px 24px 10px; flex: 1; min-height: 0; display: flex; flex-direction: column; }
.kpis { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 8px; margin-bottom: 8px; flex: none; }
.kpi { background: var(--panel); border: 1px solid var(--border); border-radius: 8px; padding: 8px 12px; box-shadow: var(--shadow); }
.kpi .label { font-size: 10px; color: var(--muted); text-transform: uppercase; letter-spacing: .04em; }
.kpi .value { font-size: 16px; font-weight: 700; margin-top: 2px; }
.tso-row { display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 8px; flex: none; }
.tso-chip { background: var(--panel); border: 1px solid var(--border); border-radius: 999px; padding: 4px 12px; font-size: 12px; box-shadow: var(--shadow); white-space: nowrap; }
.tso-chip b { font-weight: 700; }
.tso-chip .muted { color: var(--muted); }
.toolbar { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; margin-bottom: 8px; flex: none; }
.toolbar select, .toolbar input { background: var(--panel); border: 1px solid var(--border); border-radius: 8px; padding: 5px 9px; color: var(--text); font-size: 12.5px; font-family: var(--font); }
.toolbar label.date-label { font-size: 11.5px; color: var(--muted); display: flex; align-items: center; gap: 4px; }
.toolbar button { background: var(--accent); color: #fff; border: none; border-radius: 8px; padding: 6px 13px; font-size: 12.5px; cursor: pointer; }
.toolbar button.secondary { background: var(--panel); color: var(--text); border: 1px solid var(--border); }
.count { color: var(--muted); font-size: 12px; margin-left: auto; }
.table-wrap { background: var(--panel); border: 1px solid var(--border); border-radius: 10px; overflow: auto; box-shadow: var(--shadow); flex: 1; min-height: 0; }
table { border-collapse: collapse; width: auto; min-width: 100%; font-size: 12.5px; white-space: nowrap; table-layout: auto; }
th, td { padding: 6px 10px; text-align: left; border-bottom: 1px solid var(--border); }
th { position: sticky; top: 0; background: var(--panel); cursor: pointer; user-select: none; color: var(--muted); font-weight: 600; z-index: 2; position: relative; }
th:hover { color: var(--accent); }
th .arrow { opacity: .4; margin-left: 3px; }
th .resizer { position: absolute; right: 0; top: 0; width: 6px; height: 100%; cursor: col-resize; z-index: 3; }
th .resizer:hover, th .resizer.active { background: var(--accent); opacity: .5; }
.truncate { overflow: hidden; text-overflow: ellipsis; }
tbody tr:hover { background: var(--accent-soft); }
.num { text-align: right; font-variant-numeric: tabular-nums; }
footer { padding: 6px 24px; color: var(--muted); font-size: 11px; flex: none; }
footer a { color: var(--muted); }
</style>
</head>
<body>
<header>
  <div>
    <h1>POC Results Dashboard</h1>
    <div class="subtitle" id="subtitle">Last refreshed &mdash;</div>
  </div>
  <button id="theme-toggle" title="Toggle theme" aria-label="Toggle theme">&#9789;</button>
</header>
<div class="sources">
  <a class="pill" href="https://www.ofertadecapacidade.com.br/PEG/resultado" target="_blank" rel="noopener">Source: Portal de Oferta de Capacidade</a>
</div>
<main>
  <div class="kpis" id="kpis"></div>
  <div class="tso-row" id="tso-row"></div>
  <div class="toolbar">
    <select id="f-transporter"><option value="">All pipelines</option></select>
    <select id="f-type"><option value="">All transaction types</option></select>
    <select id="f-timing"><option value="">All trade timing</option></select>
    <label class="date-label">From <input id="f-date-from" type="date"></label>
    <label class="date-label">To <input id="f-date-to" type="date"></label>
    <input id="f-search" type="search" placeholder="Search process / delivery point&hellip;">
    <button class="secondary" id="btn-reset">Reset filters</button>
    <button id="btn-csv">Download CSV</button>
    <span class="count" id="row-count"></span>
  </div>
  <div class="table-wrap">
    <table id="data-table">
      <thead><tr id="thead-row"></tr></thead>
      <tbody id="tbody"></tbody>
    </table>
  </div>
</main>
<footer>
  &copy; <span id="year"></span> GasBrazil.com &middot; Data: Portal de Oferta de Capacidade (public API) &middot; Contact: <a href="mailto:eb@gasbrazil.com">eb@gasbrazil.com</a>
</footer>
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

function fmtNum(v, maxFrac) {
  if (v === null || v === undefined || v === "") return "";
  return Number(v).toLocaleString("en-US", { maximumFractionDigits: maxFrac === undefined ? 2 : maxFrac });
}

function label(col) {
  return (DATA.displayNames && DATA.displayNames[col]) || col;
}

let DATA = null;
let sortCol = "Trade Date";
let sortDir = -1;
let filtered = [];
let columnWidths = Object.assign({}, DEFAULT_COL_WIDTH);

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
// header cells (built once) and body cells (rebuilt constantly) read from it.
function makeResizable() {
  const ths = document.querySelectorAll("#thead-row th");
  ths.forEach((th, idx) => {
    const col = DATA.columns[idx];
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
      }
      document.addEventListener("mousemove", onMove);
      document.addEventListener("mouseup", onUp);
    });
  });
}

function buildHeader() {
  const tr = document.getElementById("thead-row");
  tr.innerHTML = "";
  DATA.columns.forEach((col, idx) => {
    const th = document.createElement("th");
    const span = document.createElement("span");
    span.textContent = label(col);
    th.appendChild(span);
    const arrow = document.createElement("span");
    arrow.className = "arrow";
    th.appendChild(arrow);
    th.addEventListener("click", () => {
      if (sortCol === col) sortDir *= -1; else { sortCol = col; sortDir = 1; }
      render();
    });
    tr.appendChild(th);
  });
  makeResizable();
  const ths = document.querySelectorAll("#thead-row th");
  DATA.columns.forEach((col, idx) => {
    if (columnWidths[col]) applyColWidth(ths[idx], columnWidths[col]);
  });
}

function applyFilters() {
  const transporter = document.getElementById("f-transporter").value;
  const type = document.getElementById("f-type").value;
  const timing = document.getElementById("f-timing").value;
  const dateFrom = document.getElementById("f-date-from").value;
  const dateTo = document.getElementById("f-date-to").value;
  const search = document.getElementById("f-search").value.trim().toLowerCase();
  filtered = DATA.rows.filter(r => {
    if (transporter && r["Transporter (TSO)"] !== transporter) return false;
    if (type && r["Transaction Type"] !== type) return false;
    if (timing && r["Trade Timing"] !== timing) return false;
    if (dateFrom && (!r["Trade Date"] || r["Trade Date"] < dateFrom)) return false;
    if (dateTo && (!r["Trade Date"] || r["Trade Date"] > dateTo)) return false;
    if (search) {
      const hay = ((r["codigoProcesso"] || "") + " " + (r["Delivery Point"] || "")).toLowerCase();
      if (!hay.includes(search)) return false;
    }
    return true;
  });
}

function sortRows() {
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

function renderKpis() {
  const k = DATA.kpis;
  const recent = last7dRows();
  const avg7d = mean(recent.map(r => r["R$/m3"]));
  const el = document.getElementById("kpis");
  const items = [
    ["Processes", k.processes.toLocaleString("en-US")],
    ["Trade Date Range", k.dateRange ? k.dateRange[0] + " → " + k.dateRange[1] : "—"],
    ["Avg Price, Last 7d (R$/m³)", avg7d !== null ? avg7d.toFixed(2) : "—"],
  ];
  el.innerHTML = "";
  for (const [lbl, value] of items) {
    const div = document.createElement("div");
    div.className = "kpi";
    div.innerHTML = `<div class="label">${lbl}</div><div class="value">${value}</div>`;
    el.appendChild(div);
  }
}

function renderTsoRow() {
  const recent = last7dRows();
  const byTso = {};
  for (const r of recent) {
    const tso = r["Transporter (TSO)"] || "—";
    (byTso[tso] = byTso[tso] || []).push(r);
  }
  const el = document.getElementById("tso-row");
  el.innerHTML = "";
  const tsos = Object.keys(byTso).sort();
  if (!tsos.length) {
    el.innerHTML = '<span class="muted" style="font-size:12px;color:var(--muted);">No trades in the last 7 days</span>';
    return;
  }
  for (const tso of tsos) {
    const rows = byTso[tso];
    const avg = mean(rows.map(r => r["R$/m3"]));
    const chip = document.createElement("div");
    chip.className = "tso-chip";
    chip.innerHTML = `<b>${tso}</b> &middot; ${avg !== null ? avg.toFixed(2) : "—"} R$/m³ avg &middot; ${rows.length} trade${rows.length === 1 ? "" : "s"} <span class="muted">(7d)</span>`;
    el.appendChild(chip);
  }
}

function renderTable() {
  const tbody = document.getElementById("tbody");
  const frag = document.createDocumentFragment();
  for (const row of filtered) {
    const tr = document.createElement("tr");
    for (const col of DATA.columns) {
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
  const cols = DATA.columns;
  ths.forEach((th, idx) => {
    const arrow = th.querySelector(".arrow");
    if (cols[idx] === sortCol) arrow.textContent = sortDir === 1 ? "↑" : "↓";
    else arrow.textContent = "";
  });
}

function render() {
  applyFilters();
  sortRows();
  renderTable();
  updateArrows();
}

function toCsvValue(v) {
  if (v === null || v === undefined) return "";
  const s = String(v);
  if (/[",\\n]/.test(s)) return '"' + s.replace(/"/g, '""') + '"';
  return s;
}

function downloadCsv() {
  const lines = [DATA.columns.map(c => toCsvValue(label(c))).join(",")];
  for (const row of filtered) {
    lines.push(DATA.columns.map(c => toCsvValue(row[c])).join(","));
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

function initTheme() {
  const btn = document.getElementById("theme-toggle");
  function setTheme(mode) {
    if (mode === "dark") { document.documentElement.setAttribute("data-theme", "dark"); btn.textContent = "☀"; }
    else { document.documentElement.removeAttribute("data-theme"); btn.textContent = "☽"; }
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
  document.getElementById("subtitle").textContent = "Last refreshed " + DATA.generated;
  populateSelect(document.getElementById("f-transporter"), DATA.rows.map(r => r["Transporter (TSO)"]));
  populateSelect(document.getElementById("f-type"), DATA.rows.map(r => r["Transaction Type"]));
  populateSelect(document.getElementById("f-timing"), DATA.rows.map(r => r["Trade Timing"]));
  buildHeader();
  renderKpis();
  renderTsoRow();
  render();
  for (const id of ["f-transporter", "f-type", "f-timing", "f-date-from", "f-date-to"]) {
    document.getElementById(id).addEventListener("change", render);
  }
  document.getElementById("f-search").addEventListener("input", render);
  document.getElementById("btn-reset").addEventListener("click", () => {
    document.getElementById("f-transporter").value = "";
    document.getElementById("f-type").value = "";
    document.getElementById("f-timing").value = "";
    document.getElementById("f-date-from").value = "";
    document.getElementById("f-date-to").value = "";
    document.getElementById("f-search").value = "";
    render();
  });
  document.getElementById("btn-csv").addEventListener("click", downloadCsv);
  initTheme();
}
init();
</script>
</body>
</html>
"""


def write_dashboard(out_path=DEFAULT_OUT):
    payload = load_payload()
    b64 = encode_payload(payload)
    html = TEMPLATE.replace("__PAYLOAD__", b64)
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    print(f"Wrote dashboard ({len(html):,} bytes, {len(payload['rows'])} rows) to {out_path}")


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_OUT
    write_dashboard(out)
