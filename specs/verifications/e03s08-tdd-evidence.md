# e03s08 verification evidence

<!-- story: e03s08 -->

The four ledger verifies were run on `feat/e03` after the documentation edits. For
this WSL environment, the ledger's bare `ruff` executable was run as
`.venv/bin/ruff`.

## Task 1 — CHANGELOG

Command:

```text
grep -q "augury" CHANGELOG.md
```

Result: **PASS** (exit 0).

The Unreleased entry uses `feat(dataflows)`, lists the nine mapped methods, names
all four opt-in tool categories, documents `AUGURY_BASE_URL`, and states the D3
unchanged-defaults guarantee.

## Task 2 — configuration docs

Command:

```text
grep -q "AUGURY_BASE_URL" .env.example && grep -q "augury" README.md
```

Result: **PASS** (exit 0).

`.env.example` documents the `http://localhost:8765` default and explicit-empty
disabling behavior. README documents category chains, per-method `tool_vendors`
overrides, the four opt-in categories, the running/backfilled lake prerequisite,
Augury-side `POST /data/*` jobs, and the `NO_DATA_AVAILABLE` /
`DATA_UNAVAILABLE` no-fabrication contract.

## Task 3 — knowledge refresh

Command:

```text
grep -q "augury" specs/tech-architecture/tech-stack.md \
  && grep -q "signal family" specs/product/GLOSSARY_LATEST.yaml
```

Result: **PASS** (exit 0).

The current-tree count measurements recorded in `tech-stack.md` were re-run with
these commands:

```text
find tests -type f -name 'test_*.py' | wc -l                         -> 75
 grep -Rho '@pytest.mark.unit' tests --include='*.py' | wc -l       -> 428
find tradingagents cli -type f -name '*.py' -print0 | xargs -0 cat | wc -l -> 14015
grep -Rl 'logger = logging.getLogger' tradingagents cli --include='*.py' | wc -l -> 16
grep -RIl 'monkeypatch' tests --include='*.py' | wc -l              -> 40
grep -RIl 'mock.patch' tests --include='*.py' | wc -l                -> 14
grep -Rho 'console\.print' cli --include='*.py' | wc -l            -> 72
sed -n '/^TOOLS_CATEGORIES = {/,/^}/p' tradingagents/dataflows/interface.py | grep -c '^    "' -> 10
```

The vendor-seam refresh names `augury`, its nine mapped methods, and the four
new categories. The glossary adds `data lake`, `PIT vintage`, `signal family`,
and `binding gate`.

## Task 4 — full Preflight

Commands:

```text
.venv/bin/python -m pytest -q
.venv/bin/ruff check .
```

Result: **PASS** (exit 0).

```text
1091 passed, 5 skipped, 22 warnings, 88 subtests passed
All checks passed!
```

The five skips remain the documented environmental skips (POSIX file modes,
missing optional `langchain_aws`, and missing live DeepSeek credentials).
