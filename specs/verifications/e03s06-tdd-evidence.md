# e03s06 TDD evidence

<!-- story: e03s06 -->

## RED → GREEN

The test-only RED commit was `b904ca4` (`test(augury): add signal states
contracts`, `Story: e03s06`). The required collection gate passed with six new
signal tests collected:

```text
.venv/bin/python -m pytest -q tests/test_augury_tools.py -k signal --collect-only
6/19 tests collected (13 deselected)
```

An isolated archive of that test-only commit was then run before any
implementation commits. It failed 6 tests for the intended missing seams:
`get_augury_signal_states` absent, `signal_states_tools` absent, registration
missing, and both binding/prompt gates absent. This preserves RED evidence
without changing the active branch checkout.

GREEN implementation commits, in order:

- `2a0836a` — vendor vocabulary, PIT endpoint, rendering, and graceful 422
  family validation.
- `102703c` — `signal_states` category, Augury routing registration, and
  fail-open optional-category pin.
- `0b8ad69` — tool wrapper, public export, market/fundamentals binding gate,
  and conditional analyst prompt paragraphs.

## Task verification

1. `.venv/bin/python -m pytest -q tests/test_augury_tools.py -k signal --collect-only`
   — passed; 6 signal tests collected.
2. `.venv/bin/python -m pytest -q tests/test_augury_tools.py -k 'signal and vendor'`
   — passed; 1 passed, 18 deselected.
3. `.venv/bin/python -m pytest -q tests/test_augury_tools.py -k 'registration or routing'`
   — passed; 3 passed, 16 deselected.
4. `.venv/bin/python -m pytest -q tests/test_augury_tools.py -k 'signal and (tool or binding or prompt)'
   — passed; 6 passed, 13 deselected.
5. `.venv/bin/python -m pytest -q && .venv/bin/ruff check .`
   — passed; 1080 passed, 5 skipped, 88 subtests passed; Ruff clean.

The five skips are the documented environmental skips (POSIX file modes,
optional Bedrock dependency, and absent live DeepSeek credentials). The full
suite baseline supplied for this story was 1074 passed / 5 skipped / 88
subtests, so this story adds six passing tests.

## Behavioral coverage

- Signal markdown includes triggered state, derived detail (direction/value or
  upstream detail), signal date, and formula version.
- Unknown family is rejected locally with all 13 registry families listed;
  upstream HTTP 422 is also converted to the same helpful message.
- The tool clamps `curr_date` to injected `trade_date` before routing.
- Default configuration binds neither analyst; explicit Augury configuration
  binds the same tool to market and fundamentals nodes and adds analyst-specific
  family guidance.
- The valid family vocabulary is pinned with a comment to Augury's
  `signals/registry.py`, including seven technical and six knowledge families.
