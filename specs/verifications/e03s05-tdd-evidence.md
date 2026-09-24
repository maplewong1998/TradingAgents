# e03s05 TDD evidence

<!-- story: e03s05 -->

## Scope

Implemented the opt-in Augury AI forecast and valuation pack. Kronos forecasts are
withheld when their live `data_asof` is newer than the analysis date, and both the
forecast honesty flags and valuation summary are rendered without fabricating missing
data. The two tools are bound to the market/fundamentals analysts only when Augury is
explicitly present in the category chain (including `tool_vendors` overrides). All
HTTP calls are mocked at `augury.requests.get`; no Augury service, database, or network
endpoint was started.

## RED -> GREEN evidence

| Behavior | RED evidence | GREEN evidence |
|---|---|---|
| Forecast, withholding, valuation, routing, tools, binding tests | `d397d17 test(agents): add e03s05 augury forecast contracts`; isolated vendor run initially failed 5 tests with the expected missing `get_augury_ai_forecast`, missing `get_augury_valuation`, and absent binding implementation. `--collect-only` collected 13 tests. | `f0989eb feat(agents): add e03s05 augury forecast tools`; `tests/test_augury_tools.py` passed 13 tests. |
| Existing optional-category pin | The full suite exposed the expected e03s05 contract update needed in `tests/test_augury_vendor.py`: its e03s04 exact-set assertion still pinned only the two prior optional categories. | Updated that exact-set assertion (preserving the pin) to include `ai_forecast` and `valuation`, with the e03s04/e03s05 rationale comment. |

## Task verification ledger

All six tasks are `passing` in `e03s05-tasks.yaml`; the story headers in both the task
ledger and `e03s05-ai-forecast-pack.md` are `passing`. Both `development_status.e03s05`
and `stories.e03s05` in `specs/execution-status.yaml` are `done`, with 6/6 tasks passing
and 0 failing.

1. `.venv/bin/python -m pytest -q tests/test_augury_tools.py --collect-only` — 13 tests collected.
2. `.venv/bin/python -m pytest -q tests/test_augury_tools.py -k vendor` — 5 passed, 8 deselected.
3. `.venv/bin/python -m pytest -q tests/test_augury_tools.py -k 'registration or routing'` — 2 passed, 11 deselected.
4. `.venv/bin/python -m pytest -q tests/test_augury_tools.py -k tool` — 13 passed, 0 deselected.
5. `.venv/bin/python -m pytest -q tests/test_augury_tools.py -k 'binding or prompt' && .venv/bin/python -m pytest -q tests/test_structured_agent_prompts.py` — 2 passed, 11 deselected; then 6 passed.
6. `.venv/bin/python -m pytest -q && .venv/bin/ruff check .` — 1074 passed, 5 skipped, 22 warnings, 88 subtests passed; Ruff reported `All checks passed!`.

The baseline was 1061 passed / 5 skipped / 88 subtests, so the 13-test increase is the
new story file. The five skips remain the documented environmental skips.

## Coverage of requested behaviors

- `/signals/{ticker}/kronos` renders prediction fields and the verbatim
  `data_available`, `degraded`, `stale_days`, and `data_asof` honesty block; a newer
  `data_asof` returns an explicit look-ahead refusal with both dates and no prediction
  values; `data_available=false` and 404 use `NoMarketDataError` and the router sentinel.
- `/valuation/{ticker}` renders method and `ValuationSummary` markdown tables; 404 uses
  the optional-category no-data sentinel; past analysis dates carry a live-vintage caveat.
- `ai_forecast` and `valuation` are registered in the seam and `OPTIONAL_CATEGORIES`;
  wrappers use `InjectedState("trade_date")` and `as_of` clamping.
- Tool-node binding and analyst prompt text use the same explicit Augury predicate;
  default-config nodes and prompts remain unchanged.

## Changed files

- `tradingagents/dataflows/augury.py`
- `tradingagents/dataflows/interface.py`
- `tradingagents/agents/utils/ai_forecast_tools.py`
- `tradingagents/agents/utils/agent_utils.py`
- `tradingagents/graph/trading_graph.py`
- `tradingagents/agents/analysts/market_analyst.py`
- `tradingagents/agents/analysts/fundamentals_analyst.py`
- `tests/test_augury_tools.py`
- `tests/test_augury_vendor.py` (one exact-set expectation updated for e03s05)
- `specs/epics/e03-augury-data-lake/e03s05-tasks.yaml`
- `specs/epics/e03-augury-data-lake/e03s05-ai-forecast-pack.md`
- `specs/execution-status.yaml`
- `specs/verifications/e03s05-tdd-evidence.md`

## Residual risks

- Valuation is explicitly labeled live-vintage for historical runs because the endpoint
  has no historical-vintage parameter.
- Full preflight emits existing model/runtime warnings and five documented environmental
  skips; no test failures remain.
