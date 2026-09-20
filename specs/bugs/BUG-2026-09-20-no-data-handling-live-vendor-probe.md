# BUG-2026-09-20 — `TestLoadOhlcvNoPoison` probes the live network for a vendor outage

<!-- story: e02s02 -->

**Status:** fixed — 2026-09-20
**Severity:** P2 (flaky Preflight: intermittent full-suite failure, 4 sightings; no production impact)
**Route:** `quick-fix` (test-only; production behavior unchanged, assertion unchanged)
**Discovered during:** e02s02 `develop-tdd` round 1 full-suite run (sighting #4 of the class
first logged in `BUG-2026-09-20-no-data-handling-nonhermetic-cache`), root-caused by the
verify resident in round 1 → round 2 fix.

## Symptom

```
FAILED tests/test_no_data_handling.py::TestLoadOhlcvNoPoison::test_empty_download_raises_and_does_not_cache
1 failed, 1020 passed, 2 skipped
```

Sightings 1–3 were attributed to the shared fixed cache path and fixed test-only
(`BUG-2026-09-20-no-data-handling-nonhermetic-cache`). Sighting #4 recurred **after**
that fix, so the previous root cause does not explain it. The isolated re-run of the
failing node passes, which is what made this look like a race.

## Root cause

The test mocks the download but not the **outage probe** that runs inside it:

```python
# tradingagents/dataflows/stockstats_utils.py:31-40
def raise_for_empty(symbol: str, canonical: str, what: str) -> None:
    if not vendor_reachable(_YAHOO_HOST):          # <- LIVE requests.head, 5s timeout
        raise VendorRateLimitError(f"Yahoo Finance is unreachable; no {what} was retrieved")
    raise NoMarketDataError(symbol, canonical, f"no {what}")
```

`vendor_reachable` (`tradingagents/dataflows/utils.py:67`) does
`requests.head("https://query2.finance.yahoo.com", timeout=5.0)`. A transient probe
failure (DNS blip, throttling, sandbox egress hiccup) flips the branch and raises
**`VendorRateLimitError`**, which is a *sibling* of `NoMarketDataError` under
`VendorError` (`tradingagents/dataflows/errors.py:21,25,46`) — **not a subclass**, so
`self.assertRaises(NoMarketDataError)` fails even though the empty-download path under
test behaved correctly. The test therefore depended on the live network: not a race, and
not caused by this story's diff.

## Capture (untouched baseline tree)

Full-suite `--tb=long` on the untouched baseline (`main` @ `5c7a9ac`, separate checkout,
capture kept as `/tmp/e02s02_baseline_run.txt`):

```
    def test_empty_download_raises_and_does_not_cache(self):
        empty = pd.DataFrame()
        with mock.patch.object(stockstats_utils.yf, "download", return_value=empty), \
                self.assertRaises(NoMarketDataError):
>           stockstats_utils.load_ohlcv("FAKE", "2026-01-01")
...
    if downloaded.empty or "Close" not in downloaded.columns:
>               raise_for_empty(symbol, canonical, "price rows")
...
    def raise_for_empty(symbol: str, canonical: str, what: str) -> None:
        if not vendor_reachable(_YAHOO_HOST):
>           raise VendorRateLimitError(f"Yahoo Finance is unreachable; no {what} was retrieved")
E           tradingagents.dataflows.errors.VendorRateLimitError: Yahoo Finance is unreachable; no price rows was retrieved
...
FAILED tests/test_no_data_handling.py::TestLoadOhlcvNoPoison::test_empty_download_raises_and_does_not_cache
1 failed, 1001 passed, 2 skipped, 22 warnings, 88 subtests passed in 3.84s
```

## Deterministic reproduction

The probe result is the only variable, so blocking it reproduces the failure exactly.

Mechanism, with the mocked download the test already uses:

```bash
.venv/bin/python - <<'PY'
import tempfile
from unittest import mock
import pandas as pd
from tradingagents.dataflows import stockstats_utils
from tradingagents.dataflows.config import set_config

set_config({"data_cache_dir": tempfile.mkdtemp()})
with mock.patch.object(stockstats_utils.yf, "download", return_value=pd.DataFrame()), \
     mock.patch.object(stockstats_utils, "vendor_reachable", return_value=False):
    try:
        stockstats_utils.load_ohlcv("FAKE", "2026-01-01")
    except Exception as e:
        print(f"{type(e).__name__}: {e}")
PY
```

```
VendorRateLimitError: Yahoo Finance is unreachable; no price rows was retrieved
```

The whole test module, with the live probe failing at the `requests` level:

```bash
.venv/bin/python - <<'PY'
import sys
import requests, pytest
from unittest import mock

def boom(*a, **k):
    raise requests.ConnectionError("live probe blocked")

with mock.patch.object(requests, "head", boom):
    sys.exit(pytest.main(["-q", "tests/test_no_data_handling.py"]))
PY
```

```
FAILED tests/test_no_data_handling.py::TestLoadOhlcvNoPoison::test_empty_download_raises_and_does_not_cache
1 failed, 2 passed
```

Same node, same traceback line (`stockstats_utils.py:39`), one pytest process, no
concurrency involved — which is how the class was separated from the cache-poisoning bug.

## Fix

Stub the probe in the test's `setUp`; the assertion and the production code are
untouched:

```python
self._reachable = mock.patch.object(
    stockstats_utils, "vendor_reachable", return_value=True
)
self._reachable.start()
self.addCleanup(self._reachable.stop)
```

`return_value=True` is the *correct* stub for this test's purpose: the vendor answered,
the download was empty, so an empty result is an absence (`NoMarketDataError`) — the
outage classification path belongs to its own test, not to this one.

## Regression guard

- With `requests.head` blocked, `tests/test_no_data_handling.py` stays green (pre-fix: 1 failed).
- The assertions are unchanged: an empty download with no cache must still raise
  `NoMarketDataError`, must not write a cache file, and a second call must re-fetch.
- `tradingagents/dataflows/stockstats_utils.py` behavior is deliberately unchanged here:
  the outage branch is production behavior with its own coverage.

## Follow-up worth doing (not in this fix)

- `tests/_tmp_cache` should be gitignored or banned outright — still outstanding from
  `BUG-2026-09-20-no-data-handling-nonhermetic-cache`. The directory is absent from the
  tree today and the previous fix removed the only writer, so nothing references it; the
  entry rides to e02s03 / `quick-fix`.
- `raise_for_empty` calls the network while a test is asserting a *data-absence* path:
  consider letting callers inject the reachability check so every test around it is
  hermetic without stubbing a private seam.

## Verify

```bash
.venv/bin/python -m pytest -q tests/test_no_data_handling.py
.venv/bin/python -m pytest -q
```
