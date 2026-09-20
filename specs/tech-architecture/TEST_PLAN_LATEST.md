# Test Plan — TradingAgents

**Status:** NOT YET PRODUCED — scaffolded by `bigpowers init` on 2026-09-20.
**Produced by:** `plan-tests` — one plan per P0/P1 epic at `specs/tech-architecture/eNN-TEST_PLAN_LATEST.md`.
**Waiver:** P2/P3-dominant epics may set `test_plan: waived` in `specs/state.yaml`.

## Baseline as observed (map-codebase, 2026-09-20)

| Fact | Value |
|------|-------|
| Test files | 74 |
| Tests marked `pytest.mark.unit` | ~370 |
| Tests marked `integration` | 1 |
| Tests marked `smoke` | 0 (marker declared, used by CI jobs) |
| Coverage tooling | none configured — **no coverage baseline exists** |
| Runner | `pytest` (`testpaths = ["tests"]`, `-ra --strict-markers`) |
| CI | `pytest -q` on py3.10–3.13 + clean-install import smoke + `ruff check .` |

## Recorded baseline — 2026-09-20

```
946 passed, 2 skipped, 88 subtests passed in 2.99s
ruff check . → All checks passed!
```

Environment: Python 3.12.11 (`.venv` via `uv`), pandas 3.0.6, `TZ=Asia/Shanghai`.
Skipped: `test_bedrock_provider` (no `langchain_aws` extra), `test_deepseek_reasoning`
live-API test (no real key).

**This baseline required a fix.** Establishing it surfaced 3 failures in
`test_ohlcv_cache_freshness.py` that CI cannot see — the suite was timezone-dependent
(see `specs/bugs/BUG-2026-09-20-ohlcv-cache-freshness-tz.md`). Run the baseline in a
**non-UTC** timezone, or it proves less than it appears to.

## Harness invariants (do not break these)

`tests/conftest.py` carries two **autouse** fixtures that the whole suite depends on:

1. `_dummy_api_keys` — injects a placeholder for 14 provider API-key env vars, using `os.environ.get(var) or "placeholder"` so an env var present but empty still gets the placeholder. Without it, keyless CI hangs or skips.
2. `_isolate_config` — deep-copies `DEFAULT_CONFIG` into `dataflows.config._config` before and after every test. `set_config` merges rather than clears, so without this a test that sets `tool_vendors` leaks vendor routing into later tests and makes the suite order-dependent.

## Risk-scaled priorities for the next plan

1. **Rating integrity** — `extract_rating` / `process_signal` / memory-log agreement. Pure, high-blast-radius, already partially covered (`test_rating_integrity.py`). P0.
2. **Vendor failure taxonomy under fallback** — the `route_to_vendor` loop and its NO_DATA precedence. Correct but thinly covered. P0.
3. **Checkpoint resume correctness** — thread-ID signature vs. graph shape (`test_checkpoint_lifecycle.py`, `test_checkpoint_resume.py`). P1.
4. **Structured-output fallback** — provider rejection and malformed-JSON paths. P1.
5. **CLI selection/config precedence** — `test_cli_config_precedence.py` exists; extend before any `cli/main.py` refactor. P1.

## Establish before a refactor

Add a coverage measurement and record the number in this file. A 1460-line `cli/main.py` refactor (see `tech-stack.md` § Signals 1) must not proceed against an unmeasured suite.
