# TradingAgents — AI Agents

> **Multi-agent context** — This file is the canonical project context for **Cline**, **Aider**, **OpenCode**, and other AGENTS.md-native tools. Claude Code and Cursor read it via the `CLAUDE.md` symlink.

Read CONVENTIONS.md before any GitHub or git operation.

<!-- BEGIN bigpowers:context-routing -->
## Context Routing

Load subdirectory context by file glob:

| Glob | Read |
|------|------|
| `tradingagents/agents/**` | `specs/tech-architecture/tech-stack.md` § Architecture; match the existing `create_*` closure pattern |
| `tradingagents/dataflows/**` | `specs/tech-architecture/tech-stack.md` § The vendor seam; raise the `VendorError` taxonomy, never a raw exception |
| `tradingagents/llm_clients/**` | `tradingagents/llm_clients/capabilities.py` — capabilities are declared per model, never an `if`-ladder in the client |
| `tradingagents/graph/**` | `specs/tech-architecture/IMPACT_LATEST.md` — graph shape is encoded in three places |
| `cli/**` | `specs/tech-architecture/REFACTOR_LATEST.md` — 1276-line module, treat as high risk |
| `tests/**` | `tests/conftest.py` — the autouse fixtures are load-bearing |
<!-- END bigpowers:context-routing -->

<!-- BEGIN bigpowers:learned-preferences -->
## Learned User Preferences

- (none yet — updated via `session-state`)

## Workspace Facts

- (none yet — durable facts discovered across sessions)
<!-- END bigpowers:learned-preferences -->

<!-- BEGIN bigpowers:project -->
## Project

TradingAgents is a multi-agent LLM framework that reproduces a trading firm's structure — analysts gather evidence, researchers debate it, a trader proposes a transaction, and a risk team plus portfolio manager produce a final 5-tier rating.
Stack: Python 3.10+ / LangGraph / LangChain / Typer + Rich CLI / pytest + ruff

## Commands

| Action | Command |
|--------|---------|
| Setup | `uv venv --python 3.12 .venv && uv pip install --python .venv/bin/python -e ".[dev]"` |
| Run (CLI) | `tradingagents` (installed) or `python -m cli.main` |
| Run (example) | `python main.py` |
| Test | `pytest -q` |
| Test (fast) | `pytest -q -m unit` |
| Build | `pip install .` (or `pip install -e ".[dev]"`) |
| Lint | `ruff check .` |
| Preflight | `pytest -q && ruff check .` |
| CI | `gh pr checks` (when a PR is open) |

Commands run inside the project virtualenv (`.venv/`, gitignored). Activate it with
`source .venv/bin/activate`, or prefix with `.venv/bin/`. `pytest` is a dev extra —
it is not on the system Python.

## Test

`pytest -q` — markers are strict: `unit`, `integration`, `smoke`. 74 test files.
`tests/conftest.py` has two autouse fixtures that must not be weakened: placeholder API keys for 14 providers, and a `DEFAULT_CONFIG` deep-copy reset (because `set_config` merges and leaks between tests).

## Lint

`ruff check .` — strict select (`E,W,F,I,B,UP,C4,SIM`), line length 100, E501 ignored.
`ruff format` is deliberately NOT adopted repo-wide. Do not run it.

## Build

`pip install .` — there is no compile step. CI includes a clean-install import smoke test that catches undeclared runtime dependencies.

## Architecture

`cli/` → `graph/trading_graph.py` (the `TradingAgentsGraph` facade) → `graph/setup.py` (builds the LangGraph `StateGraph`) → `agents/**` (one closure factory per node) → `agents/utils/*_tools.py` (`@tool` wrappers) → `dataflows/interface.py` (`route_to_vendor`, the only vendor seam) → `dataflows/<vendor>.py`. LLM providers sit behind the `BaseLLMClient` ABC in `llm_clients/`.
Business logic lives in agents/prompts; all external I/O goes through the vendor router.

## Conventions

- Conventional Commits with a scope (`cli`, `graph`, `agents`, `dataflows`, `llm_clients`). The real version is decided by semantic-release; never hand-track it.
- Comments explain WHY and cite the issue number. This is the codebase's strongest convention — preserve it.
- Agent nodes are closures returned by `create_*` factories, not classes. Match that shape.
- A new data vendor raises the `VendorError` taxonomy (`dataflows/errors.py`) and registers in `VENDOR_METHODS` — never add a new `except` clause to `route_to_vendor`.
- Pydantic models at every LLM boundary; `from __future__ import annotations` and PEP 604 unions elsewhere.
- All planning output goes in `specs/`. Read `specs/state.yaml` and follow `handoff.next_skill`.

## Never

- Never dismiss reproducible gate failures as pre-existing or out of scope
- Never proceed on red Preflight or red CI — invoke quick-fix or fix-bug first
- Never fabricate a tradeable rating: an unparseable decision MUST return `REVIEW`, never `Hold`
- Never silently swallow a vendor failure — every fallback path logs a warning
- Never log an API key or a full request payload
- Never import from `cli/` inside `tradingagents/` (the library must not depend on presentation)
- Never edit `scripts/` — it is a symlink to the global bigpowers install
- Never run `ruff format` repo-wide, and never edit generated artifacts or `results/`
- Never let a file in § File-Size Exceptions of CONVENTIONS.md grow further — extract first

## Agent Rules

- **Workflow Mandate:** Use bigpowers skills (e.g. `plan-work`, `develop-tdd`, `investigate-bug`) for structured work. Do not write feature code directly in response to a prompt.
- **Always Green:** Preflight (`pytest -q && ruff check .`) and CI must be green before forward work.
- Read `specs/state.yaml`, `specs/tech-architecture/tech-stack.md`, and CONVENTIONS.md before writing code.
- Write the minimum code that solves the stated problem. Nothing extra.
- Run tests after every change. Show evidence before declaring done.
- All planning output goes in `specs/`.

## Token Economy — Minimal Footprint

1. **Check existing dependencies first.** DO inspect what current dependencies already do before adding a package or writing your own code.
2. **Prefer mature, maintained libraries.** DO NOT rewrite a capability a maintained library provides without a documented reason.
3. **Copy validated patterns.** DO study how established products solve the same problem before inventing a new approach.
4. **Keep the simplest working implementation.** DO write the least code that satisfies the stated requirement. NEVER add preventive abstraction or unused config layers.
<!-- END bigpowers:project -->
