# POC Dashboard

Web dashboard for Brazil's "Oferta de Capacidade" (PEG) portal results — gas
pipeline balancing, linepack, GUS acquisition, and congestion process
auction results across the national transportadoras.

Rebuilds itself daily from the public API and republishes to
[poc.gasbrazil.com](https://poc.gasbrazil.com) via GitHub Actions + Pages.
This is the same architecture as [ons-dashboard](https://github.com/caissonpoint/ons-dashboard)
(gzip+base64 JSON payload inflated client-side into a single static HTML file
— no server, no database).

## Source

- API: `https://www.ofertadecapacidade.com.br/PEG/api/public/painel/oferta/resultado-processos`
- Site: https://www.ofertadecapacidade.com.br/PEG/resultado
- The transform logic in `poc_pipeline.py` is a Python port of the
  "Resultados (Includes Null)" Power Query in the original `POC Resultados.xlsx`
  workbook: one row per accepted bid, processes with no accepted bids get a
  single null-bid row, `finalidadeProcesso`/`formaAtendimento` are translated
  to English (falling back to the original Portuguese label for any value not
  in the translation map).
- The source API has no CORS headers, so data is fetched server-side (GitHub
  Actions) rather than client-side from the published page.

## Files

- `poc_pipeline.py` — `fetch` pulls raw JSON, `build` transforms it into
  `data/poc_results.parquet` (tidy store, checked into git for history).
- `dashboard.py` — builds `docs/index.html`, the single-file dashboard.
- `make_mock.py` — synthetic raw data for local testing without hitting the
  live API.
- `.github/workflows/refresh.yml` — daily cron (11:00 UTC) + push +
  manual dispatch: fetch → build → commit → deploy to Pages.

## Local dev

```
pip install -r requirements.txt
python make_mock.py            # or: python poc_pipeline.py fetch (needs network access to the source)
python poc_pipeline.py build
python dashboard.py
```
