# Story e03s04: Macro + prediction markets via augury (optional categories)

<!-- story: e03s04 -->

**type:** feat
**risk:** P2 (both categories are OPTIONAL_CATEGORIES — failure degrades to a sentinel, never aborts a run)
**context:** domain
**bcps:** 2
**status:** planned (e45s06 ledger — tasks start `failing`, flip only on green verify)

**Context:** The last two mapped methods, both enrichment categories the router
already treats as fail-open. Augury's `/macro` serves calendar-style rows
(`MacroItem{indicator, date, country, actual, forecast, previous,
pit_approximate}`) rather than a FRED-shaped series, so the vendor renders the
calendar honestly — including the `pit_approximate` flag — instead of
imitating a series. Augury's `/prediction-markets` caches Polymarket snapshots
with `category`/`limit` params but no free-text search, so the vendor filters
`question`/`slug` by topic keywords client-side and keeps the live-vendor
withholding rule: a past analysis date gets an explicit refusal, never stale
odds presented as current.

## Zoom-Out Check

| Module touched | Purpose | Callers | Contracts to preserve |
|---|---|---|---|
| `dataflows/augury.py` | Augury lake HTTP vendor | `route_to_vendor` | `get_augury_macro_data(indicator, curr_date, look_back_days=None)` and `get_augury_prediction_markets(topic, limit=None, curr_date=None)` match the fred/polymarket impl signatures |
| `dataflows/interface.py` | The only vendor seam | `@tool` wrappers | Registration-only; `macro_data` and `prediction_markets` stay in `OPTIONAL_CATEGORIES` — membership list unchanged |

## Requirements (delta tags, e45s29)

#### ADDED: get_macro_indicators via the lake
`GET /macro?indicator=<indicator>&days=<window>` rendered as a calendar table
(date, actual, forecast, previous) with a header naming the indicator and an
explicit "calendar-style observations" caveat plus the `pit_approximate` flag
where set — the markdown does not claim FRED-style series metadata (title,
units, frequency) the lake does not serve.

#### ADDED: get_prediction_markets via the lake
`GET /prediction-markets?limit=…` (plus `category` when the topic maps to one),
rows filtered client-side by topic keywords against `question`/`slug`, rendered
like the polymarket vendor's report (implied probability, volume, end date).
Same withholding rule as the live vendor: `curr_date < today` → an explicit
withholding message, not a fetch.

## Discovery Mandate (external API, verified)

Verified 2026-09-24 against `~/Repo_Private/augury/openapi.json`: `GET /macro`
params `indicator`, `country`, `days` (bounded), `fields`, `page`, `page_size` →
`Page_MacroItem_`; `MacroItem` fields `indicator, date, country, actual,
forecast, previous, pit_approximate`. `GET /prediction-markets` params
`category`, `limit`, `fields`, `page`, `page_size` →
`Page_PredictionMarketItem_`; item fields `market_id, question, slug, outcomes,
outcome_prices, category, end_date, volume, liquidity, active, closed`. No
`as_of` on either.

## Slopcheck

No new external packages. `requests` **[OK]** — via the e03s01 `_request` helper.

## Steps

1. RED: extend `tests/test_augury_vendor.py` (`# story: e03s04`) — macro
   calendar markdown (actual/forecast/previous columns; `pit_approximate`
   rendered; no fabricated series metadata), prediction-markets keyword
   filtering over question/slug, past-date withholding identical in spirit to
   the polymarket vendor's message, lake-down → DATA_UNAVAILABLE optional
   sentinel via the router → verify: `.venv/bin/python -m pytest -q tests/test_augury_vendor.py -k "macro or prediction" --collect-only`
2. GREEN `get_augury_macro_data` → verify: `.venv/bin/python -m pytest -q tests/test_augury_vendor.py -k macro`
3. GREEN `get_augury_prediction_markets` → verify: `.venv/bin/python -m pytest -q tests/test_augury_vendor.py -k prediction`
4. Register both methods under `"augury"`; router test proving the
   fail-open sentinel when augury is the configured optional vendor and is
   unreachable → verify: `.venv/bin/python -m pytest -q tests/test_augury_vendor.py -k "registration or routing"`
5. Full Preflight → verify: `.venv/bin/python -m pytest -q && ruff check .`

## §17 Acceptance Criteria (Gherkin)

```gherkin
# scenario: SC-e03s04-P2-01
Given macro_data configured as "augury" and a lake holding CPI calendar rows
When get_macro_indicators("cpi", curr_date) runs
Then the markdown shows date/actual/forecast/previous and marks pit_approximate rows, with no fabricated units or frequency

# scenario: SC-e03s04-P1-01
Given prediction_markets configured as "augury" and a curr_date before today
When get_prediction_markets("Fed rate cut") runs
Then odds are withheld with an explicit message, mirroring the polymarket vendor's rule

# scenario: SC-e03s04-P1-02
Given prediction_markets configured as "augury" and the lake unreachable
When get_prediction_markets runs
Then the router returns the DATA_UNAVAILABLE optional sentinel and the run continues
```

## Verification Script (Step-by-Step, UAT)

1. Run `.venv/bin/python -m pytest -q tests/test_augury_vendor.py -v -k "macro or prediction"` — all green.
2. Run `.venv/bin/python -m pytest -q` and `ruff check .` — full Preflight green.

## Out of scope

- FRED-shaped series fidelity (the lake serves calendar rows — rendered as
  such); global news / insider methods (no lake endpoints); live-vs-cached odds
  reconciliation with Polymarket.

## Risks

- **Calendar rows read as a series by agents** — mitigated by the explicit
  caveat header; asserting its presence is part of the macro tests.
- **Keyword filter missing relevant cached markets** — acceptable for an
  enrichment category; the failure mode is "fewer odds shown", never wrong odds.
- **Stale cached odds on past dates** — the withholding rule guards it
  (SC-e03s04-P1-01).
