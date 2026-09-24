# e03s03 TDD evidence

Story: e03s03 — Indicators (intersection name map) + news (client-side PIT filter)

## RED → GREEN

The RED test commit was `b0bb1f1` (`test(dataflows): add e03s03 indicator and news contracts`), with the preceding tip `c9a4c8f`. The isolated behavior run was:

```text
.venv/bin/python -m pytest -q tests/test_augury_vendor.py -k "indicator or news"
10 failed, 22 deselected
```

Failures were the intended missing `_INDICATOR_MAP`, vendor functions, and interface registrations. `git log -2 --oneline` at RED:

```text
b0bb1f1 test(dataflows): add e03s03 indicator and news contracts
c9a4c8f chore(specs): close e03s02 ledger, rotate lock to e03s03
```

The first GREEN implementation commit was `d57bad6` (`feat(dataflows): add augury indicators and PIT news`), followed by `968d55c` (`fix(dataflows): align augury map with advertised indicators`). The supervisor ruling then included `mfi → mfi_14`: although mfi is not in the prompt, it is a supported yfinance indicator (`y_finance.py:154`) and augury's standard MFI-14 (`signals/technicals.py:996`), so a free-text mfi request should use the PIT-correct lake value rather than a live fallback.

## Task verification

1. RED test collection:

   ```text
   .venv/bin/python -m pytest -q tests/test_augury_vendor.py -k 'indicator or news' --collect-only
   10/32 tests collected (22 deselected)
   ```

2. Indicator implementation:

   ```text
   .venv/bin/python -m pytest -q tests/test_augury_vendor.py -k indicator
   8 passed, 24 deselected
   ```

3. News implementation:

   ```text
   .venv/bin/python -m pytest -q tests/test_augury_vendor.py -k news
   3 passed, 29 deselected
   ```

4. Registration and fallback routing:

   ```text
   .venv/bin/python -m pytest -q tests/test_augury_vendor.py -k 'registration or routing'
   6 passed, 26 deselected
   ```

5. Full preflight:

   ```text
   .venv/bin/python -m pytest -q && .venv/bin/ruff check .
   1056 passed, 5 skipped, 22 warnings, 88 subtests passed
   All checks passed!
   ```

The branch baseline was 1046 passed / 5 skipped / 88 subtests, so this story adds 10 passing tests. The five skips remain environmental (three POSIX-mode tests, missing optional `langchain_aws`, and absent live DeepSeek credentials).

## Contract coverage

- `_INDICATOR_MAP` is pinned to `close_200_sma → sma_200`, `macd → macd_line`, `macds → macd_signal`, `macdh → macd_histogram`, `mfi → mfi_14`, `rsi → rsi_14`, and `atr → atr_14`; the comment cites `augury_record/signals/daily_features.py:121-141`.
- Unserved advertised names (`close_50_sma`, `close_10_ema`, `boll`, `boll_ub`) raise `NoMarketDataError` with the served set, allowing configured fallback routing.
- Feature requests include required `fields`, a page-one/200-row projection, and a look-back-derived `start` ending at the tool's already-clamped `curr_date`.
- News requests use a window-sized `days` value with seven days of headroom, then filter `published_at` by inclusive date before rendering; all-filtered pages raise `NoMarketDataError`.
- News markdown includes URL, tickers, title, source, summary, score, verbatim sentiment label, topics, and publication time.
- Only `VENDOR_METHODS` registration changed in the seam; no router logic changed.

## Full-suite flake and confirmation

One full-preflight attempt after the supervisor-approved mfi addition hit a transient Windows file-lock failure in the unrelated memory-log rotation test: `test_memory_log.py::TestTradingMemoryLogCore::test_rotation_prunes_oldest_resolved` failed while replacing `trading_memory.tmp` with `trading_memory.md` (`PermissionError: [WinError 5]`). The augury changes do not interact with memory-log files. The isolated test rerun passed (`1 passed`), and an independent full-preflight rerun passed (`1056 passed, 5 skipped, 88 subtests`, exit 0). If this recurs, route it to fix-bug for retry-tolerant rotation on Windows rather than weakening the test.

## Ledger/bookkeeping

- `e03s03-tasks.yaml`: story status `passing`; tasks 1–5 `passing`.
- `e03s03-indicators-news.md`: status `passing`.
- `specs/execution-status.yaml`: e03s03 `done`, 5/5 tasks passing, 0 failing.

## Review focus

Scrutinize the literal indicator map against the upstream served columns and the market analyst vocabulary, the inclusive date-only news filter (including timezone-bearing timestamps), and the fallback behavior for unmapped indicators. No live Augury server or network access was used.
