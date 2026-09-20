# Design Plan — TradingAgents

**Status:** NOT YET PRODUCED — scaffolded by `bigpowers init` on 2026-09-20.
**Produced by:** `design-interface` / `model-domain` / `deepen-architecture`.
**Visual identity:** none — this project has no `DESIGN.md` and no web surface.

## Candidate design problems (from map-codebase § Signals)

Each entry is a symptom worth a "design it twice" pass — not a decided change.

1. **Graph shape is knowledge scattered across three modules.**
   `trading_graph._run_signature()`, `GraphSetup.setup_graph()`, and `graph/checkpointer.py` each independently encode what a "run shape" is. Candidate interface: a single `RunShape` value object that owns its components *and* its signature, passed to `setup_graph` and the checkpointer. Test: could adding a 5th analyst touch exactly one file?

2. **`GraphSetup.setup_graph()` is half data-driven.**
   Node/clear/tool wiring comes from `build_analyst_execution_plan`, but the `analyst_factories` dict is four hardcoded lambdas. Candidate interface: let the execution plan carry its own factory, so registering an analyst is one declarative entry.

3. **`TradingAgentsGraph` is a 672-line facade with 37 call sites.**
   It owns LLM creation, tool nodes, graph compilation, checkpoint lifecycle, memory settlement, report saving, and signal extraction. Candidate interface: extract a `CheckpointManager` and a `MemorySettlement` collaborator, leaving the facade as orchestration. Test: can a caller use checkpointing without constructing the whole graph?

4. **`cli/main.py` at 1460 lines.**
   Deleting the CLI's tests or refactoring it is currently high-risk. Candidate interface: separate `selection` (questionary prompts), `rendering` (Rich layout), and `command` layers, with config assembly (`_build_run_config`) extracted first since it is already a pure-ish seam.

## Guardrail

Any design change here is a refactor of a working system with no coverage baseline. Per `specs/tech-architecture/TEST_PLAN_LATEST.md`, measure coverage and write characterization tests **before** restructuring. Route through `plan-refactor`, not ad-hoc edits.
