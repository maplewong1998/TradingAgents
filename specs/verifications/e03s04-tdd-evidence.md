# e03s04 TDD evidence

<!-- story: e03s04 -->

## Scope

Implemented Augury macro calendar observations and cached prediction-market reads, then
registered both methods only in `tradingagents/dataflows/interface.py`. The existing
`OPTIONAL_CATEGORIES` membership remains exactly `{"macro_data", "prediction_markets"}`.
No Augury service, database, or network endpoint was started; every HTTP call in the
story tests is mocked at `augury.requests.get`.

## RED -> GREEN commits

| Behavior | RED evidence | GREEN commit / evidence |
|---|---|---|
| Macro + prediction contract tests | `2348238 test(dataflows): specify augury macro and prediction markets`; selected run: `4 failed, 33 deselected`; failures were the expected missing `get_augury_macro_data`, missing `get_augury_prediction_markets`, and missing registration key. Collection verify collected 4 tests. | `a634590 feat(dataflows): add augury macro calendar reads`; macro verify: `1 passed, 36 deselected`. |
| Prediction-market behavior | The prediction assertions were part of the RED commit above and failed for the expected missing implementation. | `b70d6e8 feat(dataflows): add augury prediction market reads`; prediction verify: `2 passed, 35 deselected`. |
| Optional routing and registration | Registration/routing assertions were part of the RED commit above; registration failed with the expected missing Augury method key. | `21d09b5 feat(dataflows): register augury optional categories`; registration/routing verify: `6 passed, 31 deselected`. |

## Task verification ledger

All five ledger tasks are `passing` in `e03s04-tasks.yaml`; the story headers in both the
tasks ledger and `e03s04-macro-prediction-markets.md` are `passing`.

1. `.venv/bin/python -m pytest -q tests/test_augury_vendor.py -k 'macro or prediction' --collect-only` — `4/37 tests collected`.
2. `.venv/bin/python -m pytest -q tests/test_augury_vendor.py -k macro` — `1 passed, 36 deselected`.
3. `.venv/bin/python -m pytest -q tests/test_augury_vendor.py -k prediction` — `2 passed, 35 deselected`.
4. `.venv/bin/python -m pytest -q tests/test_augury_vendor.py -k 'registration or routing'` — `6 passed, 31 deselected`.
5. `.venv/bin/python -m pytest -q && .venv/bin/ruff check .` — `1061 passed, 5 skipped, 22 warnings, 88 subtests passed`; Ruff reported `All checks passed!`.

The execution-status row `e03s04` is `done` with 5/5 tasks passing and 0 failing.

## Coverage of requested behaviors

- `/macro` receives `indicator` and the configured/default `days` window and renders only
  date/actual/forecast/previous calendar columns, marking `pit_approximate` rows without
  claiming series title, units, or frequency metadata.
- `/prediction-markets` receives `limit` and a mapped category where applicable. Matching
  is client-side over question/slug; output includes implied probability, volume, and end
  date. A past `curr_date` returns an explicit withholding message without fetching.
- With Augury configured as the vendor for either optional category, an unreachable lake
  is converted by the existing router into the `DATA_UNAVAILABLE` optional sentinel.

## Changed files

- `tradingagents/dataflows/augury.py`
- `tradingagents/dataflows/interface.py`
- `tests/test_augury_vendor.py`
- `specs/epics/e03-augury-data-lake/e03s04-tasks.yaml`
- `specs/epics/e03-augury-data-lake/e03s04-macro-prediction-markets.md`
- `specs/execution-status.yaml`
- `specs/verifications/e03s04-tdd-evidence.md`

## Residual risks

- The Augury endpoint has no market vintage; current cached odds are intentionally
  withheld for past analysis dates. Macro rows retain the lake's `pit_approximate` flag.
- Full preflight emits the repository's existing model/runtime warnings and five documented
  environmental skips; no test failures occurred.
