# Story e03s01: Tracer bullet — augury vendor core + OHLCV through the seam (opt-in)

<!-- story: e03s01 -->

**type:** feat
**risk:** P0 (new external integration; every later e03 story builds on this client)
**context:** infra
**bcps:** 5
**status:** planned (e45s06 ledger — tasks start `failing`, flip only on green verify)

**Context:** TradingAgents reaches every external data source through one seam —
`route_to_vendor` in `dataflows/interface.py` — and every vendor is a module that
returns markdown strings and raises the `VendorError` taxonomy. This story adds
`dataflows/augury.py`: the HTTP client for the augury data lake (FastAPI,
canonical `http://localhost:8765`), the base-URL config surface
(`augury_base_url` + `AUGURY_BASE_URL` env override), the deterministic
ErrorResponse→taxonomy mapping, and the first mapped method — `get_stock_data`
from `/api/v1/bars/{ticker}` — registered for opt-in chains. Defaults are
untouched: a stock config never calls augury (D3). Evidence base:
`specs/product/RESEARCH-2026-09-24-augury-data-source.md`; decisions D1–D5 in
its §6.

## Zoom-Out Check

| Module touched | Purpose | Callers | Contracts to preserve |
|---|---|---|---|
| `dataflows/augury.py` (NEW) | Augury lake HTTP vendor | `route_to_vendor` via `VENDOR_METHODS` | Markdown out; `VendorError` taxonomy only; per-method signatures match existing impls |
| `dataflows/interface.py` | The only vendor seam | every `@tool` wrapper | `VENDOR_METHODS[method][vendor]` shape; no new `except` clause in `route_to_vendor`; `#988/#289` chain semantics |
| `default_config.py` | Config defaults + env overrides | graph, CLI, dataflows | `DEFAULT_CONFIG` complete; env-override map pattern (TRADINGAGENTS_DEBATE_GATE precedent); `data_vendors` chains unchanged |
| `dataflows/symbol_utils.py` | Canonical symbol normalization | existing vendors | augury normalizes through the same `normalize_symbol` before any HTTP call |

## Requirements (delta tags, e45s29)

#### ADDED: Augury vendor module
`tradingagents/dataflows/augury.py`: `get_base_url()` (lazy, `fred.get_api_key`
pattern — empty/unset raises `VendorNotConfiguredError`), `_request(path,
params)` (`requests.get`, `REQUEST_TIMEOUT = 30` per the polymarket precedent,
`response.raise_for_status()`), and error mapping from augury's frozen e51s01
`ErrorResponse{detail, code, request_id, errors[]}`: `404/not_found` →
`NoMarketDataError(symbol, detail=…)` whose detail appends "the lake may need
the matching `POST /data/*` refresh job first"; `429/rate_limited` →
`VendorRateLimitError`; connection/timeout errors propagate as-is so the router
logs them loudly (#989) and skips. **Reason for Depth:** one private `_request`
helper is the single point where the wire contract is honored — every method
gets the taxonomy mapping for free, and no method can forget it.

#### ADDED: Base-URL configuration
`augury_base_url: "http://localhost:8765"` in `DEFAULT_CONFIG` with
`AUGURY_BASE_URL` env override following the `TRADINGAGENTS_DEBATE_GATE` map
pattern; explicit empty string disables the vendor (→ `VendorNotConfiguredError`
→ router skips with a log line). Never logged (secret-adjacent).

#### ADDED: get_stock_data via the lake
`get_augury_stock(symbol, start_date, end_date)` — signature identical to the
yfinance impl. Calls `GET /api/v1/bars/{ticker}` with `start`, `end`,
`page_size=200`; augury serves newest-first pages (`AGENTS.md` gotcha 1), so
the vendor paginates to cover the window and renders oldest-first markdown.
Empty coverage → `NoMarketDataError` (the router's NO_DATA sentinel then names
the symbol and reason).

#### ADDED: Vendor registration
`"augury"` appended to `VENDOR_LIST`; `VENDOR_METHODS["get_stock_data"]` gains
`"augury": get_augury_stock`; `data_vendors` comments in `default_config.py`
list augury as an option. Registration only — no existing chain edited.

## Discovery Mandate (external API, verified)

Verified 2026-09-24 against the checked-in `~/Repo_Private/augury/openapi.json`
(the document `http://localhost:8765/docs` renders): `GET /api/v1/bars/{ticker}`
parameters `ticker*`, `start`, `end`, `fields`, `page`, `page_size`; 200 `object`,
404/422 `ErrorResponse`. `api/errors.py` `ERROR_CODE_MAP`: `{400/422:
validation_error, 404: not_found, 409: conflict, 413: payload_too_large, 429:
rate_limited, 500: internal_error}`. Lake pagination is newest-first with
`page`/`page_size` max 200 (`AGENTS.md` gotcha 1: "never pass `size`"). Reads are
cache-first — a 404 can mean the matching `POST /data/ohlcv` job never ran
(README "Analysis read endpoints").

## Slopcheck

No new external packages. `requests` **[OK]** — existing pinned dependency, same
client style as `polymarket.py`/`fred.py`.

## Steps

1. RED: create `tests/test_augury_vendor.py` (`# story: e03s01`) — base-url
   matrix (env unset → default; env set → honored; empty →
   `VendorNotConfiguredError`), error mapping (404 `ErrorResponse` →
   `NoMarketDataError` with the job-hint detail; 429 → `VendorRateLimitError`;
   `ConnectionError` propagates unchanged), stock-data markdown (newest-first
   pages reversed to chronological; second page fetched when the window
   exceeds one page), and registration invariants. `requests.get` mocked at the
   `augury` module boundary (house pattern) → verify: `.venv/bin/python -m pytest -q tests/test_augury_vendor.py --collect-only`
2. GREEN core: `dataflows/augury.py` — module docstring (boundary + PIT
   posture), `get_base_url()`, `_request()` with the ErrorResponse mapping and
   `#989`-style loud logging → verify: `.venv/bin/python -m pytest -q tests/test_augury_vendor.py -k "base_url or error"`
3. GREEN stock: `get_augury_stock` — `normalize_symbol` first, paginated bars,
   chronological markdown table → verify: `.venv/bin/python -m pytest -q tests/test_augury_vendor.py -k stock`
4. Registration + config: `VENDOR_LIST`, `VENDOR_METHODS["get_stock_data"]`,
   `augury_base_url` + `AUGURY_BASE_URL` in `default_config.py`, `data_vendors`
   comment lists augury → verify: `.venv/bin/python -m pytest -q tests/test_augury_vendor.py -k "registration or config" && .venv/bin/python -m pytest -q tests/test_env_overrides.py`
5. Routing integration tests: chain `"augury,yfinance"` — augury 404 falls
   through to a mocked yfinance impl; augury connection error logs a warning
   and skips; chain `"augury"` alone with 404 returns the NO_DATA sentinel
   naming the symbol and detail; default config never touches augury (no HTTP
   call made) → verify: `.venv/bin/python -m pytest -q tests/test_augury_vendor.py -k routing`
6. Full Preflight → verify: `.venv/bin/python -m pytest -q && ruff check .`

## §17 Acceptance Criteria (Gherkin)

```gherkin
# scenario: SC-e03s01-P0-01
Given data_vendors core_stock_apis is "augury,yfinance" and the lake answers bars
When the market analyst calls get_stock_data
Then the markdown table comes from augury bars in chronological order and yfinance is never called

# scenario: SC-e03s01-P0-02
Given the chain "augury,yfinance" and augury 404s the ticker
When get_stock_data runs
Then yfinance serves and the augury NoMarketDataError detail names the POST /data/ohlcv job hint

# scenario: SC-e03s01-P0-03
Given the chain "augury" and the lake is unreachable
When get_stock_data runs
Then the failure is logged loudly (#989) and the run surfaces the vendor error for this core category

# scenario: SC-e03s01-P1-01
Given AUGURY_BASE_URL is unset
When the vendor resolves its base URL
Then it uses http://localhost:8765; when set to "" it raises VendorNotConfiguredError

# scenario: SC-e03s01-P1-02
Given a stock default_config
When any augury-mapped method is invoked
Then no HTTP request to the lake is ever attempted
```

## Verification Script (Step-by-Step, UAT)

1. Run `.venv/bin/python -m pytest -q tests/test_augury_vendor.py -v` — all scenarios pass with requests mocked.
2. Run `.venv/bin/python -m pytest -q` — full suite green (no regression in `test_env_overrides.py`, routing tests).
3. Run `ruff check .` — "All checks passed!".
4. Optional live smoke (lake running): `set AUGURY_BASE_URL=http://localhost:8765` then a `set_config({"data_vendors": {"core_stock_apis": "augury"}})` snippet call prints augury bars markdown for a backfilled ticker.

## Out of scope

- Every method beyond `get_stock_data` (e03s02–e03s04); new tool categories
  (e03s05–e03s07); docs (e03s08).
- Augury-side changes of any kind; triggering `POST /data/*` jobs from TA.

## Risks

- **Wire drift** (augury changes its contract) — detected by the mocked
  ErrorResponse-shape tests pinning `code` values; augury's own Bruno suite owns
  the server side.
- **Pagination silently truncating a window** — detected by the multi-page test;
  newest-first reversal asserted explicitly.
- **Base URL leaking into logs** — `_request` logs status/code only, never the
  URL with query params; asserted in the error-mapping tests.
- **Opt-in leaking into defaults** — SC-e03s01-P1-02 guards it: stock config =
  zero lake traffic.
