# e03s01 TDD evidence

## Environment and Phase 0

- Host/shell: Windows host with WSL bash and WSL git.
- Python discovery in WSL: `/usr/bin/python3.14` only; the orchestrator provisioned the
  Windows CPython 3.12.13 uv environment and POSIX venv shims because WSL DNS could not
  resolve `astral.sh`.
- Effective story environment: `.worktrees/e03-augury-data-lake/.venv/bin/python`,
  Python 3.12.13; editable install resolves `tradingagents` to this worktree.
- Worktree: `.worktrees/e03-augury-data-lake`, branch `feat/e03`, based on `main` at
  `10cfdf9`.
- Planning capsule was restored from the `e03-planning-artifacts` stash and committed as
  `f89b85b` before story implementation.

## Baseline on main

Commands:

```text
.venv/bin/python -m pytest -q
.venv/bin/ruff check .
```

Result: **1024 passed, 5 skipped, 88 subtests passed**; ruff reported **All checks passed!**.
The five skips are the documented environment skips (three POSIX file mode tests, missing
`langchain_aws`, and missing live DeepSeek key).

## RED evidence

The test-only commit was `617d13b` (`test(dataflows): add augury vendor tracer tests`;
`Story: e03s01`).

```text
.venv/bin/python -m pytest -q tests/test_augury_vendor.py --collect-only
15 tests collected
```

Immediately after the test-only commit, the isolated test run failed **15/15** with the
expected missing implementation/config/registration reasons: `ModuleNotFoundError` for
`tradingagents.dataflows.augury`, missing `augury_base_url`, and absent `augury` registration.
The RED run exited 1. The last-two commit log at RED was:

```text
617d13b test(dataflows): add augury vendor tracer tests
f89b85b docs(specs): plan e03 augury data lake integration
```

The repository's verification script was not used because this environment's `scripts/`
symlink is not an executable local TDD harness; manual isolated RED output and `git log -2`
were captured as the accepted substitute.

## GREEN task verification

All six ledger verifies passed before their corresponding ledger flips:

1. `...pytest -q tests/test_augury_vendor.py --collect-only` — **15 tests collected**.
2. `...pytest -q tests/test_augury_vendor.py -k 'base_url or error'` — **5 passed, 10 deselected**.
3. `...pytest -q tests/test_augury_vendor.py -k stock` — **5 passed, 10 deselected**.
4. `...pytest -q tests/test_augury_vendor.py -k 'registration or config'` — **2 passed, 13 deselected**; then `...pytest -q tests/test_env_overrides.py` — **23 passed**.
5. `...pytest -q tests/test_augury_vendor.py -k routing` — **4 passed, 11 deselected**.
6. Full preflight below — **passed**.

The implementation commit was `39399a1` (`feat(dataflows): add augury stock vendor seam`;
`Story: e03s01`).

## Final preflight

Commands:

```text
.venv/bin/python -m pytest -q
.venv/bin/ruff check .
```

Result: **1039 passed, 5 skipped, 88 subtests passed**; ruff reported **All checks passed!**.
The 15-test increase over baseline is the new augury vendor contract suite. Existing five
environmental skips remained unchanged.

## Story commits

```text
39399a1 feat(dataflows): add augury stock vendor seam
617d13b test(dataflows): add augury vendor tracer tests
f89b85b docs(specs): plan e03 augury data lake integration
```

## Deviations and risks

- WSL could not bootstrap uv because DNS resolution for `astral.sh` was unavailable. The
  orchestrator supplied the verified Windows uv-managed CPython 3.12.13 environment and
  POSIX shims; no Python 3.14 fallback was used.
- No augury server was started and no live HTTP call was made. All HTTP behavior is mocked
  at `tradingagents.dataflows.augury.requests`.
- The story deliberately registers augury only for `get_stock_data`; later stories own
  the remaining mapped methods.
