# BUG-2026-09-20 — `TestLoadOhlcvNoPoison` is non-hermetic: shared fixed cache path

<!-- story: e02s01 -->

**Status:** fixed — 2026-09-20
**Severity:** P2 (flaky Preflight: 1 full-suite failure in 15 observed runs; no production impact)
**Route:** discovered defect → `quick-fix` (test-only, root cause reproduced deterministically)
**Discovered during:** e02s01 `verify-work` full-suite runs (recorded by the gate audit,
`specs/verifications/AUDIT-e02-e02s01.md` § Discovered defect)

## Symptom

One full-suite run out of fifteen reported:

```
FAILED tests/test_no_data_handling.py::TestLoadOhlcvNoPoison::test_empty_download_raises_and_does_not_cache
1 failed, 999 passed, 2 skipped
```

The test passed in isolation and in the next 14 full-suite runs. The story diff was
causally excluded: `tests/test_no_data_handling.py` and
`tradingagents/dataflows/stockstats_utils.py` are untouched by `534782e..HEAD`.
The gate audit classified it as a non-hermetic test and routed a BUG log + hermeticity fix.

## Root cause

`setUp` points the dataflow config at a **fixed shared path** and never purges it:

```python
def setUp(self):
    self._tmp = os.path.join(os.path.dirname(__file__), "_tmp_cache")   # fixed, in-tree
    os.makedirs(self._tmp, exist_ok=True)                              # keeps leftovers
    set_config({"data_cache_dir": self._tmp})
```

`tests/_tmp_cache` is not a pytest `tmp_path`, is not gitignored, and is not emptied
before the test. When a non-empty, fresh `FAKE-YFin-data.csv` is already present —
left over from an interrupted run (whose `tearDown` never ran), or written by a
concurrent pytest process sharing the same worktree — `load_ohlcv` serves that cache and
returns normally instead of raising:

```python
# tradingagents/dataflows/stockstats_utils.py:226-243
if data_file is not None and _cache_is_fresh(data_file):
    return cached_frame          # <- the test's mocked empty download never runs
```

So the first assertion fails: `NoMarketDataError not raised`.

## Deterministic reproduction (replaces "not reproducible")

```bash
mkdir -p tests/_tmp_cache
printf 'Date,Open,High,Low,Close,Volume\n2026-01-01,1,1,1,1,1\n' \
  > tests/_tmp_cache/FAKE-YFin-data.csv
.venv/bin/python -m pytest -q tests/test_no_data_handling.py::TestLoadOhlcvNoPoison
```

Before the fix:

```
E               AssertionError: NoMarketDataError not raised
FAILED tests/test_no_data_handling.py::TestLoadOhlcvNoPoison::test_empty_download_raises_and_does_not_cache
1 failed in 0.25s
```

`tearDown` then deletes the shared directory, which is why the *next* run is green — the
observed 1-then-14-greens pattern. The trigger is environmental (residual state or a
concurrent run), which is exactly why 14 reruns could not reproduce it and the planted
file can.

## Fix

Give each test its own directory and remove it unconditionally (test-only, assertion
unchanged):

```python
def setUp(self):
    self._tmp = tempfile.mkdtemp(prefix="ta-no-data-handling-")
    set_config({"data_cache_dir": self._tmp})

def tearDown(self):
    shutil.rmtree(self._tmp, ignore_errors=True)
```

A unique path per test is immune both to residual state and to a second pytest process;
`ignore_errors=True` also survives a leftover directory that `os.rmdir` used to choke on.

## Regression guard

- The planted-file reproduction above must PASS after the fix (no shared path to poison).
- `.venv/bin/python -m pytest -q tests/test_no_data_handling.py` stays green, and the
  assertions (`NoMarketDataError` raised, nothing cached, second call re-fetches) are
  unchanged.

**Follow-up worth doing (not in this fix):** `tests/_tmp_cache` should be gitignored or
banned outright — a test that writes into the worktree can be read by any other test or
process. Consider a conftest guard that points `data_cache_dir` at `tmp_path` for the
whole suite.

## Verify

```bash
.venv/bin/python -m pytest -q tests/test_no_data_handling.py
.venv/bin/python -m pytest -q
```
