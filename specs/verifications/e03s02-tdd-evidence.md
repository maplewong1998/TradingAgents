# e03s02 TDD evidence

## RED isolation

RED commit: `ed84cda test(dataflows): add e03s02 PIT fundamentals RED tests`

Command:

```text
.venv/bin/python -m pytest -q tests/test_augury_vendor.py -k 'fundamentals or balance_sheet or cashflow or income_statement'
```

Result: **FAIL (2 failed, 18 deselected)**. The two initial behavior tests failed with
`AttributeError` because `get_augury_fundamentals` and
`get_augury_income_statement` did not exist yet. This is the intended missing-
implementation failure; no network was called.

Isolation log immediately after RED:

```text
ed84cda test(dataflows): add e03s02 PIT fundamentals RED tests
df6fd0d chore(specs): acquire e03s02 lock, hand off to develop-tdd
```

## GREEN evidence

- Task 1 `--collect-only`: **5/22 tests collected**, exit 0.
- Task 2 `-k fundamentals`: **1 passed, 21 deselected**, exit 0.
- Task 3 `-k 'balance_sheet or cashflow or income_statement'`: **4 passed, 18 deselected**, exit 0.
- Task 4 `-k 'registration or routing'`: **5 passed, 17 deselected**, exit 0.
- Task 5 full preflight: **1046 passed, 5 skipped, 88 subtests passed**; `.venv/bin/ruff check .` passed. The initial bare `ruff` invocation failed only because WSL PATH does not include `.venv/bin`; rerunning with the verified `.venv/bin/ruff` shim passed.
