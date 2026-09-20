# BUG-2026-09-20 — OHLCV cache-freshness tests fail in any non-UTC timezone

<!-- story: e01s01 -->

**Status:** fixed — 2026-09-20
**Severity:** P1 (red Preflight blocks forward work; CI cannot catch it)
**Route:** discovered defect → `quick-fix` (single-file, test-only, root cause proven)
**Discovered during:** bigpowers bootstrap, establishing the test baseline

## Symptom

```
tests/test_ohlcv_cache_freshness.py::test_current_day_cache_past_ttl_is_not_fresh FAILED
tests/test_ohlcv_cache_freshness.py::test_a_download_from_an_earlier_day_is_not_fresh FAILED
tests/test_ohlcv_cache_freshness.py::test_load_ohlcv_refetches_stale_same_day_cache FAILED

3 failed, 943 passed, 2 skipped
```

Green in CI (Ubuntu, `TZ=UTC`), red on a workstation at `UTC+08:00`.

## Root cause

The test helper and the code under test disagree about what a naive timestamp means.

`tests/test_ohlcv_cache_freshness.py::_write` writes the fake mtime with pandas:

```python
written = NOW.timestamp() - age_seconds      # NOW is tz-naive
os.utime(f, (written, written))
```

`tradingagents/dataflows/stockstats_utils.py::_cache_is_fresh` reads it back with `fromtimestamp`:

```python
written = pd.Timestamp.fromtimestamp(os.path.getmtime(data_file))
```

In pandas 3.0 these two are **not inverses for a tz-naive input**:

| Call | Naive input interpreted as | Observed (UTC+08:00) |
|------|---------------------------|----------------------|
| `pd.Timestamp("2026-07-18 12:00").timestamp()` | **UTC** | `1784376000` |
| `pd.Timestamp.fromtimestamp(1784376000)` | **local** | `2026-07-18 20:00` |

So every `_write(age_seconds=N)` lands `N + utcoffset` seconds in the **future** relative
to `now`. With `age_seconds = STALE` (960) at UTC+08:00, `_cache_is_fresh` computes
`(now - written)` as `-27,840 s`, which is `<= OHLCV_CACHE_TTL_SECONDS` (900), so a stale
cache is reported **fresh**. At `TZ=UTC` the offset is zero and the tests pass.

Measured directly:

```
tz local offset: +0800
pandas .timestamp()  -> 1784376000.0  (treats naive as UTC in pandas 3.0)
stdlib .timestamp()  -> 1784347200.0  (treats naive as LOCAL)
fromtimestamp(pandas-epoch) -> 2026-07-18 20:00:00
fromtimestamp(stdlib-epoch) -> 2026-07-18 12:00:00
```

## Why CI is green

`.github/workflows/ci.yml` runs on `ubuntu-latest` with `TZ=UTC`, where the offset is 0 and
the two conventions coincide. **The suite is timezone-dependent and CI structurally cannot
detect it.** Any contributor east or west of UTC sees 3 spurious failures.

## Not a production bug

`load_ohlcv` is internally consistent: `now = pd.Timestamp.today()` is local-naive and
`pd.Timestamp.fromtimestamp(getmtime)` is local-naive, so the comparison is correct in every
timezone. Only the test's epoch construction is wrong. Verified by inspection of
`stockstats_utils.py::_cache_is_fresh` and `load_ohlcv`.

## Fix

Make the helper build the epoch with the same (local) semantics the reader uses, via stdlib
`datetime.timestamp()` on a naive datetime:

```python
written = NOW.to_pydatetime().timestamp() - age_seconds
```

One line, test-only. Production code is unchanged.

## Regression guard

- `tests/test_ohlcv_cache_freshness.py` must pass under a non-UTC `TZ`.
- Verify: `TZ=Asia/Shanghai .venv/bin/python -m pytest tests/test_ohlcv_cache_freshness.py -q`
  AND `TZ=UTC .venv/bin/python -m pytest tests/test_ohlcv_cache_freshness.py -q`.

**Follow-up worth doing (not in this fix):** CI runs only `TZ=UTC`, so this class of bug is
invisible there. Consider adding a non-UTC job, or a `tzset`-based autouse fixture, for tests
that touch mtime arithmetic.

## Verify

```bash
TZ=Asia/Shanghai .venv/bin/python -m pytest tests/test_ohlcv_cache_freshness.py -q
.venv/bin/python -m pytest -q
```
