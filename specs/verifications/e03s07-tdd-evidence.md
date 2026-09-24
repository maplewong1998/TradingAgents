# e03s07 TDD evidence

Story: e03s07 — Cross-sectional context, analyst-bound (D5)

## Contract evidence

- `augury/openapi.json` (2026-09-24): `GET /liquidity/{ticker}` exposes only
  `window_days`; it has no `as_of` or `vintage` parameter. Liquidity is therefore
  treated as live-vintage-only and withheld when the requested analysis date is
  historical. The implementation test pins both the no-request historical path
  and the live request shape.
- `POST /api/v1/batch/feature-vector` requires `FeatureVectorBatchRequest` with
  `tickers` (1–500), optional `as_of`, and `vintage`; `FeatureVectorResponse`
  carries `items` and per-ticker `failed` strings. The vendor sends one ticker,
  forwards the PIT date, and renders a failed slot as `not available: <reason>`.
- `GET /api/v1/universe` requires `as_of` and accepts `q`; the upstream contract
  documents PIT membership with delisted members included. The vendor renders
  member, present-but-delisted, and absent as distinct statuses.

## RED -> GREEN

- RED commit `9a76489`: test-only contracts for liquidity, feature vectors,
  universe trichotomy, registration, clamping, binding, prompts, and PM graph
  integrity. Isolation run: `7 failed, 23 deselected`; failures were the
  expected missing vendor functions (`AttributeError`), while collection passed
  (`7/30 tests collected`).
- GREEN commit `aa40f27`: added the three vendor functions, POST request seam,
  optional registration, wrappers, analyst bindings, and conditional prompts.
  Targeted vendor tests: `7 passed, 23 deselected`; binding/prompt tests:
  `8 passed, 22 deselected`.
- Follow-up test pin `98946bc`: updated the single permitted
  `OPTIONAL_CATEGORIES` assertion in `tests/test_augury_vendor.py`, citing
  e03s07.
- Graph-integrity test `b700a70`: pins the unchanged 21-node/12-unconditional-
  edge graph shape and asserts no Portfolio Manager ToolNode. Targeted binding
  tests remain `8 passed, 22 deselected`.

## Frozen task verifies

1. `.venv/bin/python -m pytest -q tests/test_augury_tools.py -k 'liquidity or feature_vector or universe' --collect-only`
   — `7/30 tests collected`.
2. `.venv/bin/python -m pytest -q tests/test_augury_tools.py -k 'vendor and (liquidity or feature_vector or universe)'`
   — `7 passed, 23 deselected`.
3. `.venv/bin/python -m pytest -q tests/test_augury_tools.py -k 'registration or routing'`
   — `4 passed, 26 deselected`.
4. `.venv/bin/python -m pytest -q tests/test_augury_tools.py -k 'cross_sectional or binding or prompt'`
   — `8 passed, 22 deselected`.
5. `.venv/bin/python -m pytest -q && .venv/bin/ruff check .`
   — `1091 passed, 5 skipped, 22 warnings, 88 subtests passed`; Ruff `All checks passed!`.

The final count is baseline `1080 passed / 5 skipped / 88 subtests` plus the
story's new coverage. Skips are the five documented environmental skips; no
Augury server, PostgreSQL, network, or live HTTP call was used.
