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

Recorded below as each task's frozen `verify:` command exits zero.
