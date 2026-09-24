# Story e03s05: AI forecast pack — get_ai_forecast + get_valuation tools

<!-- story: e03s05 -->

**type:** feat
**risk:** P0 (look-ahead-bias guard on a forward-looking signal is decision-path integrity)
**context:** domain
**bcps:** 5
**status:** passing (e45s06 ledger — all 6 tasks green)

**Context:** The first augury-only capability (D1): the lake's Kronos AI price
forecasts and multi-method valuations have no TradingAgents counterpart, so
they arrive as two new tools rather than vendor registrations. Both endpoints
are **live-vintage only** — Kronos' `KronosResponse` carries `data_asof`,
`stale_days`, `degraded`, `data_available`, `torch_available`; `/valuation`
404s when no cached fundamentals exist — so the vendor applies the polymarket
discipline: a forecast whose `data_asof` is later than the analysis date is
look-ahead information and is withheld with an explicit explanation, and every
degradation flag is rendered verbatim. The tools are bound to the market and
fundamentals analysts **only when their categories are configured** (D3 binding
gate): a stock config binds nothing and the analyst prompts stay byte-identical.

## Zoom-Out Check

| Module touched | Purpose | Callers | Contracts to preserve |
|---|---|---|---|
| `dataflows/augury.py` | Augury lake HTTP vendor | `route_to_vendor` | New functions `get_augury_ai_forecast(ticker, curr_date)`, `get_augury_valuation(ticker, curr_date)`; markdown out; taxonomy only |
| `dataflows/interface.py` | The only vendor seam | `@tool` wrappers | New categories `ai_forecast` + `valuation` added to `TOOLS_CATEGORIES`, `VENDOR_METHODS`, and `OPTIONAL_CATEGORIES` (fail-open); existing entries untouched |
| `agents/utils/ai_forecast_tools.py` (NEW) | `@tool` wrappers | analysts, `agent_utils.__all__` | House pattern: `InjectedState("trade_date")` + `as_of(curr_date, trade_date)` clamp (macro_data_tools.py precedent) |
| `graph/trading_graph.py` `_create_tool_nodes` | Per-analyst ToolNodes | `TradingAgentsGraph.__init__` | Binding gate: augury tools appended only when the category's configured chain names augury; every bound tool is executable in its node (verified-snapshot precedent) |
| `agents/analysts/market_analyst.py` / `fundamentals_analyst.py` | Prompt composition | graph nodes | Augury paragraph appended only when the matching tools are bound; default-config prompts byte-identical |

## Requirements (delta tags, e45s29)

#### ADDED: get_ai_forecast tool (market analyst)
`@tool get_ai_forecast(ticker, curr_date)` → vendor → `GET
/signals/{ticker}/kronos`. Renders `predicted_return_pct`, `forecast_window`,
`bull_signal`/`bear_signal`/`neutral_signal`, `upside_probability`,
`model_name`, and the honesty block (`data_available`, `degraded`,
`stale_days`, `data_asof`) verbatim. **Withholding rule:** `data_asof` later
than the as_of-clamped analysis date ⇒ return an explicit look-ahead refusal,
no forecast content. `data_available=false` or 404 ⇒ the optional-category
unavailable path, never an invented forecast.

#### ADDED: get_valuation tool (fundamentals analyst)
`@tool get_valuation(ticker, curr_date)` → `GET /valuation/{ticker}` →
`ValuationResponse` with per-method results and
`ValuationSummary{average_value, median_value, min_value, max_value,
undervalued_count, …, current_price, average_premium_discount,
margin_of_safety}` rendered as a markdown table; 404 (no cached fundamentals)
⇒ unavailable sentinel. Live-vintage caveat stated in the header when the
analysis date is in the past.

#### ADDED: Binding gate
`_create_tool_nodes` appends each new tool only when `"augury"` appears in the
configured chain for its category (`data_vendors`, `tool_vendors` override
honored); analyst factories append the matching prompt paragraph under the same
condition. **Reason for Depth:** the gate is what makes D3 honest — opt-in
governs routing *and* tool existence *and* prompt text through one config read,
so a default run is provably unchanged.

## Discovery Mandate (external API, verified)

Verified 2026-09-24 against `~/Repo_Private/augury/openapi.json`: `GET
/signals/{ticker}/kronos` params `ticker*`, `model_name` → `KronosResponse`
with `ticker, data_available, torch_available, hint, model_name, predicted_at,
forecast_window, predicted_return_pct, forecast_volatility, bull_signal,
bear_signal, neutral_signal, upside_probability, forecast_series, data_asof,
stale_days, degraded`. `GET /valuation/{ticker}` param `ticker*` →
`ValuationResponse`; README: "Valuation methods (404 when no cached
fundamentals)".

## Slopcheck

No new external packages. `requests` **[OK]** — via the e03s01 `_request` helper.

## Steps

1. RED: create `tests/test_augury_tools.py` (`# story: e03s05`) — forecast
   markdown with all Kronos flags rendered; **withholding** when
   `data_asof > trade_date` (SC-e03s05-P0-01); `data_available=false` →
   unavailable path; valuation table + 404 sentinel; binding gate: default
   config binds neither tool and prompts are byte-identical, configured
   categories bind them and prompt paragraphs appear → verify: `.venv/bin/python -m pytest -q tests/test_augury_tools.py --collect-only`
2. GREEN vendor: `get_augury_ai_forecast` (withholding + honesty block) and
   `get_augury_valuation` in `dataflows/augury.py` → verify: `.venv/bin/python -m pytest -q tests/test_augury_tools.py -k vendor`
3. Seam: `TOOLS_CATEGORIES` + `VENDOR_METHODS` + `VENDOR_LIST` entries;
   `ai_forecast` and `valuation` added to `OPTIONAL_CATEGORIES` with a comment
   (enrichment, fail-open) → verify: `.venv/bin/python -m pytest -q tests/test_augury_tools.py -k "registration or routing"`
4. GREEN tools: `agents/utils/ai_forecast_tools.py` (@tool wrappers with
   `InjectedState("trade_date")` + `as_of` clamp); export via
   `agents/utils/agent_utils.py` `__all__` → verify: `.venv/bin/python -m pytest -q tests/test_augury_tools.py -k tool`
5. Binding gate + prompts: `_create_tool_nodes` conditional append;
   market/fundamentals analyst factories append the augury paragraph only when
   bound; assert default-config prompts byte-identical → verify: `.venv/bin/python -m pytest -q tests/test_augury_tools.py -k "binding or prompt" && .venv/bin/python -m pytest -q tests/test_structured_agent_prompts.py`
6. Full Preflight → verify: `.venv/bin/python -m pytest -q && ruff check .`

## §17 Acceptance Criteria (Gherkin)

```gherkin
# scenario: SC-e03s05-P0-01
Given a backtest dated 2026-01-15 and a Kronos forecast whose data_asof is 2026-09-20
When get_ai_forecast runs
Then the forecast is withheld with an explicit look-ahead explanation and no prediction numbers appear

# scenario: SC-e03s05-P1-01
Given data_vendors ai_forecast="augury" and a live forecast with degraded=true
When the market analyst calls get_ai_forecast
Then the markdown renders predicted_return_pct, the three signal flags, upside_probability, and a verbatim degraded/stale_days honesty block

# scenario: SC-e03s05-P1-02
Given valuation configured and the lake 404s (no cached fundamentals)
When get_valuation runs
Then the router returns the optional-category DATA_UNAVAILABLE sentinel and the run continues

# scenario: SC-e03s05-P0-02
Given a stock default_config
When the analyst ToolNodes are built
Then neither augury tool is bound and both analyst prompts are byte-identical to today's
```

## Verification Script (Step-by-Step, UAT)

1. Run `.venv/bin/python -m pytest -q tests/test_augury_tools.py -v` — all green.
2. Run `.venv/bin/python -m pytest -q` and `ruff check .` — full Preflight green.
3. Optional live smoke (lake up, `data_vendors: {ai_forecast: "augury"}`): run an
   analysis on a Kronos-covered ticker and observe the forecast section in the
   market report, flags included.

## Out of scope

- Kronos fine-tuning or model management (lake-side `POST /data/kronos*`);
  valuation method selection; signal families (e03s06); any PM surface.

## Risks

- **Look-ahead via live-vintage forecast in backtests** — guarded by
  SC-e03s05-P0-01; the refusal text names both dates so the leak is visible if
  the rule ever misfires.
- **Binding-gate drift** (tool bound but prompt silent, or vice versa) — both
  sides read the same config predicate; tests assert the matrix.
- **Degraded forecast read as reliable** — the honesty block is mandatory
  markdown, asserted verbatim in tests.
