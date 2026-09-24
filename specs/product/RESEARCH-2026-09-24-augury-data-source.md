# RESEARCH — Augury as a TradingAgents data source (research-first)

> Task: understand the current data flow and find prior art before wiring in
> augury (`~/Repo_Private/augury`) as a new data source. Evidence-first: every
> claim cites a file. Verdict at the bottom; nothing here is implementation.

## 1. How the current data flow works

```
analyst closure (agents/analysts/*.py, prompt lists the tools)
    → @tool wrapper (agents/utils/*_tools.py) — adds as_of(curr_date, trade_date) PIT clamp
    → route_to_vendor(method, *args)          — dataflows/interface.py, the ONLY vendor seam
    → VENDOR_METHODS[method][vendor]          — one vendor module per source
```

Facts that constrain the integration:

- **Tool surface = 11 methods in 6 categories** (`interface.py` `TOOLS_CATEGORIES`):
  `get_stock_data`, `get_indicators`, `get_fundamentals`, `get_balance_sheet`,
  `get_cashflow`, `get_income_statement`, `get_news`, `get_global_news`,
  `get_insider_transactions`, `get_macro_indicators`, `get_prediction_markets`.
- **Vendor chain is config, not code.** `data_vendors` (per category) and
  `tool_vendors` (per method, wins) in `default_config.py`; a comma list is the
  explicit fallback chain; `"default"` = all registered. No silent fallback to
  unconfigured vendors (#988/#289).
- **Error contract = behavior-typed taxonomy** (`dataflows/errors.py`):
  `NoMarketDataError` (empty/stale → `NO_DATA_AVAILABLE` sentinel),
  `VendorRateLimitError` (skip to next vendor), `VendorNotConfiguredError`
  (skip; surfaced if nothing else serves). Any other exception is logged loudly
  and skipped (#989). `OPTIONAL_CATEGORIES = {macro_data, prediction_markets}`
  degrade to a sentinel instead of raising.
- **Vendors return markdown strings** for the LLM, not dataframes. Fixed
  per-method signatures (from existing impls):
  - `get_stock_data(symbol, start_date, end_date)`
  - `get_indicators(symbol, indicator, curr_date, look_back_days)`
  - `get_fundamentals(ticker, curr_date=None)`
  - `get_balance_sheet / get_cashflow / get_income_statement(ticker, freq="quarterly", curr_date=None)`
  - `get_news(ticker, start_date, end_date)` / `get_global_news(curr_date, look_back_days, limit)`
  - `get_insider_transactions(ticker, curr_date=None)`
  - `get_macro_indicators(indicator, curr_date, look_back_days=None)`
  - `get_prediction_markets(topic, limit=None, curr_date=None)`
- **PIT discipline already exists at two layers**: the `@tool` wrapper clamps
  dates via `date_window.as_of`, and vendors self-censor when they only serve
  live data (polymarket withholds odds when `curr_date < today`).
- **Anomaly:** `sentiment_analyst.py:47-48` imports `dataflows/reddit.py` and
  `stocktwits.py` directly — they bypass the seam. Not a template to copy;
  a known exception and a future cleanup candidate.

## 2. Augury surface (from `augury/README.md`, `AGENTS.md`, `openapi.json`)

- One FastAPI app (`python -m augury_record.api`, canonical port 8765),
  no auth on reads (loopback/homelab deployment), checked-in `openapi.json`,
  errors as `{"detail": ...}`; 404 = not cached/found, 422 = bad params.
- **PIT-native**: `?as_of=` on fundamentals/financials/signals/universe,
  `?version=vYYYYMMDD` vintage pins on features, `ingested_at <= as_of`
  knowledge-time gating. List endpoints are newest-first `Page[T]`
  (`?page=&page_size=`, max 200). `/api/v1/watermarks` = freshness probes.
- **Cache-first reads**: data appears only after the matching `POST /data/*`
  job ran. A 404 can mean "never backfilled" as much as "unknown symbol".
- Endpoint → schema highlights:
  - `GET /api/v1/bars/{ticker}` (`start,end,fields,page`) — v4 daily bars
  - `GET /api/v1/features/{ticker}` (`fields` required, `version`) — v2 adds
    sma_5/10/100/200, ema_20/50, stoch_k/d/j_14, mfi_14, cci_20, donchian_*, obv_20_ratio
  - `GET /api/v1/fundamentals/{ticker}` (`as_of` required) — PIT snapshot
  - `GET /api/v1/financials/{ticker}` (`as_of` required, `fields`, Page) — PIT facts
  - `GET /news/{ticker}` (`days`) — `NewsItem`: title, source, summary,
    sentiment_score/label, topics, published_at
  - `GET /macro` (`indicator,country,days`) — `MacroItem`: actual/forecast/previous,
    `pit_approximate` (calendar-style, not a FRED-shaped series)
  - `GET /prediction-markets` (`category,limit`) — cached Polymarket snapshot
  - No existing-category match: `/api/v1/signals/{ticker}` (family+as_of:
    regime/hurst/ms_drx/sentiment/quality/growth), `/signals/{ticker}/kronos`
    (predicted_return_pct, bull/bear/neutral, upside_probability, degraded flag),
    `/valuation/{ticker}` (multi-method + summary), `/social/{ticker}`
    (sentiment-scored posts), `/liquidity/{ticker}`, `/api/v1/universe`,
    `POST /api/v1/batch/feature-vector`.

## 3. Method mapping (fit check)

| TA method | Augury endpoint | Fit |
|---|---|---|
| `get_stock_data` | `/api/v1/bars/{ticker}` (start/end) | Clean; must flip newest-first pages to chrono markdown |
| `get_indicators` | `/api/v1/features/{ticker}` (fields, version) | Good; needs stockstats-name → augury-column map; one call per indicator |
| `get_fundamentals` | `/api/v1/fundamentals/{ticker}?as_of=curr_date` | Excellent — PIT beats yfinance's present-day snapshot |
| `get_balance_sheet` / `get_cashflow` / `get_income_statement` | `/api/v1/financials/{ticker}` | Probable — must confirm facts distinguish statement + freq (open Q6) |
| `get_news` | `/news/{ticker}?days=` | Good, sentiment-scored; no `as_of` → filter `published_at` client-side by `curr_date` |
| `get_global_news` | — none | **No fit**; keep yfinance/alpha_vantage |
| `get_insider_transactions` | — read endpoint absent (`POST /data/insider` is a job) | **No fit** today |
| `get_macro_indicators` | `/macro?indicator=&days=` | Partial — calendar rows (actual/forecast/previous), not a series; markdown contract needs rework |
| `get_prediction_markets` | `/prediction-markets` | Good — and being lake-cached, it may serve PIT where live Polymarket cannot |

## Prior Art

| Candidate | Source | Verdict | Notes |
|-----------|--------|---------|-------|
| Vendor seam `route_to_vendor` + `VENDOR_METHODS` | `tradingagents/dataflows/interface.py` | **extend** | Register `"augury"` per method; zero router changes — the seam was designed for exactly this |
| `VendorError` taxonomy | `tradingagents/dataflows/errors.py` | **adopt** | Map augury 404/empty → `NoMarketDataError` (with `detail` from `{"detail": ...}` or `/watermarks`); unset base URL → `VendorNotConfiguredError`; never a new `except` clause |
| `polymarket.py` vendor module | `tradingagents/dataflows/polymarket.py` | **extend** | Template: `requests` + 30s timeout + module docstring + markdown report + PIT self-censorship |
| `fred.py` `get_api_key()` config pattern | `tradingagents/dataflows/fred.py:91` | **adopt** | Same shape for `AUGURY_BASE_URL` (default `http://localhost:8765`) |
| Existing `@tool` wrappers | `tradingagents/agents/utils/*_tools.py` | **adopt** | No tool/prompt changes needed for mapped methods — config alone routes them to augury |
| augury_record HTTP API | `~/Repo_Private/augury` (`openapi.json`, README) | **compose** | Consume over HTTP; `requests` is already a TA dependency — **zero new packages** |
| Direct `augury_record` package import | `~/Repo_Private/augury/src` | **rejected** | Would drag polars/sqlmodel/PG into TA, couple to its 35-table schema, and violates both repos' "one API app" boundary. Blocker: augury pins Python ≥3.12, TA supports 3.10–3.13 |
| opensrc cache | n/a | n/a | Augury is a local first-party repo, not a registry package — read directly; no new dependency to look up |
| `reddit.py` / `stocktwits.py` direct imports | `agents/analysts/sentiment_analyst.py:47` | **build later** | Seam-bypass anomaly; augury `/social/{ticker}` is the natural replacement — separate initiative |

**Overall verdict: compose + extend.** One new module
`tradingagents/dataflows/augury.py` (HTTP client → markdown, raising the
existing taxonomy), registered in `VENDOR_METHODS`; selection happens entirely
through `data_vendors` config strings. No router, tool, prompt, or dependency
changes for the mapped methods.

## 4. What a build would touch (scope preview, not a plan)

- **Phase A (small, seam-only):** `dataflows/augury.py` + `VENDOR_METHODS`
  entries + `default_config.py` comments + `.env.example` + tests mocking
  `requests` at the boundary (house pattern). Candidate methods: stock data,
  indicators, fundamentals, news, prediction markets (+ financials pending Q6).
- **Phase B (separate initiative, wide blast radius):** new categories/tools
  for augury-only signals (kronos forecast, valuation, signal families, social)
  — touches `TOOLS_CATEGORIES`, new `*_tools.py`, `trading_graph.py`
  `_create_tool_nodes`, analyst prompts, CLI config.

## 5. Open questions for elaborate-spec / grill-with-docs

1. Which methods land in Phase A — the six mapped, or a subset?
2. **404 semantics**: augury 404 = "not cached" OR "unknown ticker". Should the
   vendor surface "run `POST /data/ohlcv` first" in the `NoMarketDataError`
   detail, and/or probe `/api/v1/watermarks` before declaring NO_DATA?
3. Config surface: env var name (`AUGURY_BASE_URL`?), default, precedence vs
   `data_vendors` strings; how does a stopped lake degrade (per-call
   `VendorNotConfiguredError`-style sentinel vs loud error)?
4. PIT gaps: `/news/{ticker}` has no `as_of` — client-side `published_at <=
   curr_date` filter, or accept live-only like polymarket's withholding rule?
5. `/macro` is calendar-shaped (actual/forecast/previous) — fit for the
   FRED-shaped "series title/units/frequency/change" markdown contract, or skip?
6. Does `/api/v1/financials` distinguish statement type and annual/quarterly
   frequency? (Determines whether the 3 statement methods map.)
7. Indicator vocabulary: which stockstats indicator names must the augury
   column map cover on day one?
8. Multi-asset: augury coverage universe (US only? HK/CN via futu/akshare
   providers) vs TA's `asset_type` support.

## 6. Grill outcomes (grill-with-docs, 2026-09-24)

Doc-grounded challenges resolved against augury's canonical docs (`openapi.json`
= `http://localhost:8765/docs`, `README.md`, router source):

- **C1 — 404 semantics RESOLVED**: augury's e51s01 contract is a frozen
  `ErrorResponse{detail, code, request_id, errors[]}` (`api/errors.py`,
  `ERROR_CODE_MAP`: 404→`not_found`, 429→`rate_limited`). Wire mapping is
  deterministic: 404→`NoMarketDataError` (detail nudges "run the matching
  `POST /data/*` job first"), 429→`VendorRateLimitError`, unreachable/unset
  base URL→`VendorNotConfiguredError`.
- **C2 — financials fit CONFIRMED**: `routers/v1/pit.py:128-156` serves rows
  with a `statement` field, "period_end descending, then statement ascending,
  newest restatement per metric", PIT on `report_date/period_end/ingested_at
  <= as_of`. All three statement methods map.
- **C3 — indicator vocabulary PARTIAL**: augury serves `rsi_14`, `macd`
  (12/26/9), `ema_12/20/26/50`, `sma_5/10/100/200`, `atr_14`, `hurst_100`,
  stoch/mfi/cci/donchian/obv (`daily_features.py:121-141` + README v2 list).
  TA advertises `close_50_sma`, `close_10_ema`, `boll`, `boll_ub`
  (`market_analyst.py:28-42`) — **augury has no sma_50, ema_10, or Bollinger
  columns**. Decision D4 below.
- **C4 — coverage is HK-centric by default**: `data/universe.py:69-108`
  `DEFAULT_UNIVERSE_PLAN` = futu + hkex (stocks/ETF/fund); US only if
  explicitly backfilled. Reads are cache-first. "Augury as default primary"
  rejected → decision D3.
- **C5 — sentiment analyst is not a tool loop**: `sentiment_analyst.py:47-88`
  pre-fetches reddit/stocktwits and injects prompt blocks. `/social` wiring
  would be a data-path refactor, not a tool addition → excluded by D1.
- **C6 — no vendor config surface exists**: `data_vendors` is settable only via
  `set_config()` dict-merge (`dataflows/config.py`); no env/CLI exposure.
  Scope add: `AUGURY_BASE_URL` env + documented `set_config` snippet, following
  the `TRADINGAGENTS_DEBATE_GATE` env-override precedent (e02s03, S5).

### Decisions (user, 2026-09-24)

| # | Decision | Choice |
|---|----------|--------|
| D1 | Capability scope | **AI forecast pack + Signal-family pack + Cross-sectional pack**. Social pack excluded — reddit/stocktwits direct imports stay as-is |
| D2 | Agent wiring | **Distribute to existing agents** — no new analyst node. Per-ticker tools → analysts (market ← kronos/signal families; fundamentals ← valuation/quality); cross-sectional tools (batch feature-vector, universe, liquidity) → Portfolio Manager level. `setup_graph`, `conditional_logic`, and the debate gate's four-report assumption are untouched |
| D3 | Routing default | **Opt-in only** — `default_config.py` unchanged; augury enabled per category via `data_vendors` strings (e.g. `"augury,yfinance"`). New config surface: `AUGURY_BASE_URL` (default `http://localhost:8765`) + docs |
| D4 | Indicator gap | **Intersection-only name map** (rsi→rsi_14, macd→macd trio, close_200_sma→sma_200, …); unmapped advertised indicators return the standard NO_DATA sentinel. Zero augury-side schema changes |
| D5 | Cross-sectional placement (added at plan-work — the confirmed "zero graph changes" constraint conflicted with the PM-level reading) | **Analyst-bound, per-ticker**: market ← get_liquidity + get_feature_vector; fundamentals ← get_universe_membership. No PM tool loop, no new edges. Evidence: `create_portfolio_manager(llm)` takes no tools; only the four analysts have ToolNodes (`trading_graph.py:203-243`) |

### House-convention assertions (uncontested)

- New augury-only categories follow the `OPTIONAL_CATEGORIES` fail-open
  pattern — enrichment never aborts a run (`interface.py`).
- `/news/{ticker}` has no `as_of` — vendor filters `published_at <= curr_date`
  client-side (polymarket withholding-rule precedent).
- TA is a **read-only consumer** of the lake; it never triggers `POST /data/*`
  jobs (augury AGENTS.md: jobs are the lake's own scheduling domain).
- Kronos `degraded`/`data_available` flags are rendered honestly in markdown —
  never smoothed over (matches the codebase's no-fabrication rule).

### Out of scope (explicit)

Social pack (sentiment analyst refactor), augury-side schema changes, CLI
vendor picker, TA-triggered lake jobs, changes to graph shape/rating/risk path.

## Handoff

- Spine complete 2026-09-24: scope-work (SCOPE_LATEST.yaml, initiative
  augury-data-lake-integration) → slice-tasks (e03s01–s08, 28 BCPs,
  epics/e03-augury-data-lake/) → plan-work (specs + failing TDD ledgers).
  `planning-status.yaml` discover checklist reset and completed for e03.
- Next skill per `state.yaml` handoff: `kickoff-branch` — **HARD STOP in
  effect** (user instruction): no branch, no code without an explicit go-ahead.
