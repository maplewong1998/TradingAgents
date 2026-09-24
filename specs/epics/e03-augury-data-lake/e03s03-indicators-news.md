# Story e03s03: Indicators (intersection name map) + news (client-side PIT filter)

<!-- story: e03s03 -->

**type:** feat
**risk:** P1 (core feature logic; the name map is a documented partial contract)
**context:** domain
**bcps:** 3
**status:** passing (e45s06 ledger — all tasks green)

**Context:** Two mapped methods with known shape gaps the grill settled. (1)
`get_indicators`: augury serves feature columns `rsi_14`, `macd` (12/26/9),
`ema_12/20/26/50`, `sma_5/10/100/200`, `atr_14`, `hurst_100`, stoch/mfi/cci/
donchian/obv — but the market analyst advertises `close_50_sma`, `close_10_ema`,
`boll`, `boll_ub`, which the lake does not serve (C3). Per D4 the vendor maps
the exact intersection by name and declines the rest with `NoMarketDataError`
so a configured fallback (e.g. yfinance/stockstats) serves them. (2) `get_news`:
the lake's `/news/{ticker}` has no `as_of` — only `days` — so the vendor filters
`published_at <= curr_date` client-side, the same withholding discipline the
polymarket vendor applies to live-only data.

## Zoom-Out Check

| Module touched | Purpose | Callers | Contracts to preserve |
|---|---|---|---|
| `dataflows/augury.py` | Augury lake HTTP vendor | `route_to_vendor` | `get_augury_indicators(symbol, indicator, curr_date, look_back_days)` and `get_augury_news(ticker, start_date, end_date)` match the existing impl signatures; unmapped indicator ⇒ `NoMarketDataError`, never a wrong-column guess |
| `dataflows/interface.py` | The only vendor seam | `@tool` wrappers | Registration-only: two new `"augury"` keys |
| `agents/analysts/market_analyst.py` | Indicator vocabulary advertised in the prompt | graph node | Prompt text unchanged — the vendor declines unmapped names so the fallback serves them |

## Requirements (delta tags, e45s29)

#### ADDED: Indicator name map + get_indicators via the lake
A single `_INDICATOR_MAP` dict in `augury.py` (comment cites the lake's
`daily_features.py` serving columns) covering the exact intersection — e.g.
`rsi → rsi_14`, `macd/macds/macdh → macd 12/26/9 columns`,
`close_200_sma → sma_200`. Any other advertised name raises
`NoMarketDataError(symbol, detail="augury does not serve indicator '<name>';
served set: …")` so the router's fallback can serve it. `GET
/api/v1/features/{ticker}` is called with `fields=<mapped columns>` (required
param), `end=curr_date`, `start` derived from `look_back_days`, `version`
defaulting to current.

#### ADDED: get_news via the lake with client-side PIT
`get_augury_news(ticker, start_date, end_date)` → `GET /news/{ticker}` with
`days` sized to the window; rows are `NewsItem{url, tickers, title, source,
summary, sentiment_score, sentiment_label, topics, published_at}` rendered as
markdown with the sentiment label kept verbatim — filtered to
`start_date <= published_at <= end_date` client-side because the endpoint has
no `as_of`. An all-filtered page is `NoMarketDataError`, not an empty table.

## Discovery Mandate (external API, verified)

Verified 2026-09-24 against `~/Repo_Private/augury/openapi.json` + README:
`GET /api/v1/features/{ticker}` — `fields` **required**, `version=vYYYYMMDD`
pin optional; V2 serving columns per README § "Daily feature serving" and
`signals/daily_features.py:121-141` (`rsi` window 14, `macd` fast=12 slow=26
signal=9, `ema_12/26`, `atr_14`, `hurst_100`, plus V2 `sma_5/10/100/200`,
`ema_20/50`, `stoch_*`, `mfi_14`, `cci_20`, `donchian_*`, `obv_20_ratio`).
`GET /news/{ticker}` params `ticker*`, `days`, `fields`, `page`, `page_size` →
`Page_NewsItem_`; no `as_of` exists.

## Slopcheck

No new external packages. `requests` **[OK]** — via the e03s01 `_request` helper.

## Steps

1. RED: extend `tests/test_augury_vendor.py` (`# story: e03s03`) — name-map
   hits render the mapped columns; advertised-but-unserved names
   (`close_50_sma`, `close_10_ema`, `boll`, `boll_ub`) raise
   `NoMarketDataError` whose detail lists the served set; news rows outside
   `[start_date, end_date]` or after the analysis date are excluded; sentiment
   labels render verbatim → verify: `.venv/bin/python -m pytest -q tests/test_augury_vendor.py -k "indicator or news" --collect-only`
2. GREEN `_INDICATOR_MAP` + `get_augury_indicators` (fields projection,
   look-back window, single-page assert for the default window) → verify: `.venv/bin/python -m pytest -q tests/test_augury_vendor.py -k indicator`
3. GREEN `get_augury_news` with the client-side `published_at` filter → verify: `.venv/bin/python -m pytest -q tests/test_augury_vendor.py -k news`
4. Register both methods; routing test: chain `"augury,yfinance"` — an unmapped
   indicator falls through to the mocked yfinance impl, a mapped one is served
   by augury alone → verify: `.venv/bin/python -m pytest -q tests/test_augury_vendor.py -k "registration or routing"`
5. Full Preflight → verify: `.venv/bin/python -m pytest -q && ruff check .`

## §17 Acceptance Criteria (Gherkin)

```gherkin
# scenario: SC-e03s03-P1-01
Given chain "augury,yfinance" for technical_indicators
When the analyst requests "rsi"
Then augury serves the rsi_14 column and yfinance is never called

# scenario: SC-e03s03-P1-02
Given the same chain
When the analyst requests "close_50_sma"
Then augury declines with NoMarketDataError naming the served set and yfinance answers instead

# scenario: SC-e03s03-P0-01
Given a backtest run dated 2026-01-15 and augury news items published up to today
When get_news runs
Then only items with published_at on or before 2026-01-15 appear in the markdown
```

## Verification Script (Step-by-Step, UAT)

1. Run `.venv/bin/python -m pytest -q tests/test_augury_vendor.py -v -k "indicator or news"` — all green.
2. Run `.venv/bin/python -m pytest -q` and `ruff check .` — full Preflight green.
3. Optional live smoke: opt `technical_indicators` into `"augury,yfinance"` and request `boll` — the log shows the augury decline and the yfinance answer.

## Out of scope

- Extending the lake's served columns (D4 — an augury-side, versioned change);
- changing the market analyst's advertised vocabulary; macro/prediction markets
  (e03s04).

## Risks

- **Silent vocabulary drift** (lake adds/renames columns) — the map is pinned
  by tests against literal column names; drift surfaces as test failure, not
  wrong data.
- **News day-window over/under-fetching** (`days` is coarse) — bounded by the
  client-side date filter; under-fetch risk is mitigated by sizing `days` from
  the window with headroom and asserting the filter, not the count.
- **Look-ahead via news on backtests** — SC-e03s03-P0-01 guards it; same
  discipline as the polymarket withholding rule.
