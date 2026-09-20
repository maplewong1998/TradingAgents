# Refactor Plan — TradingAgents

**Status:** NOT YET PRODUCED — scaffolded by `bigpowers init` on 2026-09-20.
**Produced by:** `plan-refactor` (interview → tiny commits) → `specs/REFACTOR_LATEST.md`.

## Candidates, ranked by (impact ÷ risk)

| # | Target | Why | Risk |
|---|--------|-----|------|
| 1 | `specs/` ADR backfill | Decisions live only in code comments + issue numbers; cheap to preserve | none (docs) |
| 2 | Coverage baseline | No measurement exists; blocks every other refactor safely | none (tooling) |
| 3 | `cli/main.py` split | 1460 lines, largest file, wide blast radius | high |
| 4 | Extract `RunShape` value object | Removes graph-shape duplication in 3 modules | medium |
| 5 | Make analyst registration fully data-driven | `setup_graph` hardcodes 4 factory lambdas | medium |
| 6 | Extract checkpoint + memory collaborators from `TradingAgentsGraph` | 672-line facade, 37 call sites | high |

**Do not start 3, 4, 5, or 6 before 2.** There is no coverage number today, so a refactor cannot prove it preserved behavior.

## Method

Use `plan-refactor`: interview to bound the change, then land it as tiny commits that each keep Preflight green (`pytest -q && ruff check .`). Every step needs a `verify:` command and a characterization test written first.
