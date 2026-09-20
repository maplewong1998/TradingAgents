# TradingAgents — Tech Stack & Architecture

<!-- story: e01s01 -->
<!-- story: e02s03 — the Debate Gate node, the flow diagram and the stale counts in
     § Observability, § Testing, § Type safety, § Gaps and § Signals notes 1 and 3 were
     refreshed from the code in this pass. Each count is a line/marker count taken with
     grep on this tree; where a count disagreed with the earlier one it was re-measured
     rather than adjusted. -->

> Derived by `map-codebase` on 2026-09-20 from the `.codegraph` index plus targeted
> reads of manifests, entry points, and gray-area modules. Cold analysis only: every
> claim below traces to a file in this repo. Where the code surprised the scan, it is
> called out under § Signals rather than smoothed over.

## Stack

| Layer | Choice |
|-------|--------|
| Language | Python `>=3.10` (CI matrix: 3.10, 3.11, 3.12, 3.13) |
| Agent orchestration | LangGraph `>=0.4.8` (`StateGraph`, `MessagesState`, `ToolNode`) |
| LLM abstraction | LangChain (`langchain-core`, `langchain-openai`, `langchain-anthropic`, `langchain-google-genai`) |
| Checkpointing | `langgraph-checkpoint-sqlite` (`SqliteSaver`) |
| Data | `pandas`, `yfinance`, `stockstats`, `requests` |
| CLI | `typer` + `rich` + `questionary` |
| Config | `python-dotenv`, `pytz` |
| Optional | `langchain-aws` (Bedrock; `pip install "tradingagents[bedrock]"`) |
| Dev | `pytest`, `pytest-subtests`, `ruff>=0.15` |

Entry points:

- **CLI** — `tradingagents = "cli.main:app"` (`pyproject.toml`), implemented with Typer in `cli/main.py`.
- **Library** — `main.py` at the repo root is a 12-line usage example, not a production entry point.
- **Package** — `tradingagents/` (framework) and `cli/` (presentation) are the two shipped packages.

## Architecture

Layered by responsibility, with a hyper-modular agent layer and a single facade for a run.

```
cli/main.py  (Typer + Rich)
    │  gather selections → build config → stream graph events → render/save
    ▼
tradingagents/graph/trading_graph.py   ← FACADE: TradingAgentsGraph
    │  creates LLM clients, tool nodes, graph, memory log, checkpointer
    │  propagate() → create_run_state() → stream → record_decision()
    ▼
tradingagents/graph/setup.py           ← GraphSetup.setup_graph()
    │  builds the StateGraph from a selected-analyst execution plan
    ▼
Analysts → Debate Gate ─┬─ (aligned → debate skipped) ──────────┐
                        └─ (contested) → (Bull/Bear debate) ────┴→ Research Manager → Trader
        → (Aggressive/Neutral/Conservative risk debate) → Portfolio Manager → END

    │  Debate Gate = tradingagents/agents/gate/ — judges analyst alignment,
    │  routes with Command; policy: debate_gate always|auto|never
    ▼
tradingagents/agents/**   ← one factory per node, each returns a partial node fn
    │  factories bind an LLM (quick or deep) and a prompt
    ▼
tradingagents/agents/utils/*_tools.py  ← LangChain @tool wrappers
    ▼
tradingagents/dataflows/interface.py   ← route_to_vendor(): the ONLY vendor seam
    ▼
tradingagents/dataflows/<vendor>.py    ← yfinance, alpha_vantage, fred, sec_edgar,
                                         polymarket, reddit, stocktwits
tradingagents/llm_clients/**           ← provider clients behind BaseLLMClient ABC
```

Key structural facts:

- **Business logic lives in the agent/prompt layer; I/O lives in `dataflows/`.** Nodes never call `yfinance` directly — they call `@tool` wrappers, which call `route_to_vendor`, which dispatches to a vendor module. This is the codebase's one clean boundary.
- **`TradingAgentsGraph` is the only facade.** 37 call sites (CLI, `main.py`, `backtest.py`) construct it. Node wiring, LLM creation, checkpoint lifecycle, memory, and report saving all hang off it.
- **Agents are closures, not classes.** Each `create_*` factory captures its LLM and returns a `functools.partial(node, name=...)`. There is no agent base class or registry.
- **The graph is rebuilt, not mutated, for checkpoints.** `setup_graph()` returns an un-compiled `StateGraph`; `begin_checkpoint()` recompiles it with a `SqliteSaver` and `end_checkpoint()` restores the plain compile.
- **State is one flat `AgentState`** (`agents/utils/agent_states.py`) extending `MessagesState`, carrying every report, both debate states, and run context.
- **The debate is conditional, but the loop behind it is not.** `create_debate_gate` (`agents/gate/debate_gate.py`) returns a `Command` straight into the debate or straight to the Research Manager; once Bull is entered, `conditional_logic.should_continue_debate` governs the rounds exactly as before. A judge failure routes into the debate, so the gate can only ever remove LLM calls it was explicitly told to remove.

Data flow of a run (`TradingAgentsGraph.propagate`):

1. `_validate_trade_date` normalizes the date.
2. `checkpoint_scope(...)` computes a thread ID from ticker + date + `_run_signature` (analysts, debate depth, risk depth, asset type, portfolio fingerprint, `gate=<debate_gate mode>`) and recompiles the graph if checkpointing is on.
3. `create_run_state(...)` resolves pending memory entries, injects `past_context` (lessons known as of the trade date), `instrument_context` (deterministic ticker identity), and `portfolio_context`.
4. The graph streams; each analyst loops through its `ToolNode` then clears messages.
5. `process_signal(final_trade_decision)` extracts the 5-tier rating via a deterministic regex heuristic — **no second LLM call**.
6. `record_decision(...)` logs the decision to the memory log; reports are written by `reporting.write_report_tree`.

### The vendor seam

`dataflows/interface.py` holds `TOOLS_CATEGORIES`, `VENDOR_METHODS`, and `route_to_vendor(method, *args, **kwargs)`. Selection is per-category (`data_vendors`) with per-method override (`tool_vendors`). **The configured list *is* the fallback chain** — there is deliberately no silent fallback to unconfigured vendors (#988/#289). The loop catches the `VendorError` taxonomy and reacts by behavior:

| Exception | Router reaction |
|-----------|-----------------|
| `VendorRateLimitError` | Skip to next vendor; remembered for the final message |
| `VendorNotConfiguredError` | Skip; surfaced if nothing else serves the call |
| `NoMarketDataError` | Skip; if any vendor reports it, the whole call returns a NO_DATA sentinel |
| any other `Exception` | Logged loudly (#989), skipped — a broken primary must stay visible |

This is the codebase's best-designed abstraction: a new vendor raises the base types and needs no new `except` clause.

## Conventions (Observed)

These are patterns the code actually follows, not aspirations.

### Error handling

- **One exception hierarchy per concern.** `dataflows/errors.py` defines `VendorError` → `NoMarketDataError` / `VendorRateLimitError` / `VendorNotConfiguredError`. The taxonomy is explicitly sized to "the number of distinct router reactions, not the number of human-describable causes".
- `VendorNotConfiguredError` multiply-inherits `ValueError` for backward compatibility with callers that already caught `ValueError`.
- **Fail-open on enrichment, fail-closed on data.** Deterministic identity resolution and macro lookups swallow failure and annotate the prompt; price/fundamental data returns an explicit sentinel so the agent reports "unavailable" instead of inventing a value.
- **Never swallow silently.** Every fallback path in `route_to_vendor` and `agents/utils/structured.py` logs a warning; `first_error` is retained so a NO_DATA verdict cannot hide a broken primary.
- CLI-level errors are surfaced to the user through Rich panels; there is no global exception handler in the library.

### Structured output and fallbacks

`agents/utils/structured.py` centralizes the canonical three-step pattern used by the Research Manager, Trader, and Portfolio Manager:

1. `bind_structured(llm, Schema, name)` wraps with `with_structured_output`; returns `None` on `NotImplementedError`/`AttributeError` (older Ollama models).
2. `invoke_structured_or_freetext(...)` runs the structured call, renders the Pydantic result to markdown, and **falls back to plain `llm.invoke` on any exception** — the pipeline never blocks.
3. A `None` parsed result is treated as a structured miss (thinking models answer in prose) and triggers the same fallback.

The `NO_EXTERNAL_TOOLS` constant exists because schema-only binding means a model reaching for a search tool emits an unknown tool call and discards the whole structured attempt (#1130).

### Rating integrity

`agents/utils/rating.py` is the single 5-tier vocabulary (Buy/Overweight/Hold/Underweight/Sell), shared by the Research Manager, Portfolio Manager, signal processor, and memory log so they cannot drift. `extract_rating` is a two-pass NFKC-normalized regex heuristic (labelled rating last-wins, else a unique standalone rating word). **Unparseable decisions return the `REVIEW` sentinel, never a fabricated `Hold`** (#1170) — a decision nobody can read is not a neutral position. Callers must guard with `is_review` before mapping onto `PortfolioRating`.

### Type safety

- `from __future__ import annotations` plus PEP 604 unions (`str | None`) throughout the newer modules.
- Pydantic `BaseModel` at every LLM boundary (`agents/schemas.py`, `portfolio.py`) with `field_validator` coercion for nullish numbers.
- `BaseLLMClient` is an ABC (`get_llm`, `validate_model` abstract) — the one place DIP is applied deliberately.
- No `mypy`/`pyright` in CI. 31 `Any`/`type: ignore`/`noqa` markers across the whole source tree (14 `: Any`, 11 `Any]`, 6 `noqa`, 0 `type: ignore`), concentrated at LangChain interop points and in `cli/stats_handler.py`. Types are a documentation aid here, not a gate.

### Provider capability table

`llm_clients/capabilities.py` is a declarative `ModelCapabilities` table (frozen dataclass) keyed by exact model ID then forward-compat regex, replacing model-name `if`-ladders in the clients. It encodes real provider quirks: DeepSeek thinking models reject `tool_choice`, MiniMax M2.x needs `reasoning_split=True`, OpenRouter's `deepseek/` namespace is stripped to reuse native quirks (#1199).

### Observability

- **Stdlib `logging` with module-level `logger = logging.getLogger(__name__)`** in 15 modules. No structured/JSON logging, no correlation IDs, no log aggregation config.
- The CLI owns presentation: 72 `console.print(...)` calls across 5 `cli/` modules that import Rich, with `cli/stats_handler.py` as a callback handler streaming token/cost stats into the live display.
- No health-check endpoint (it is a CLI/library, not a service). Dockerfile and `docker-compose.yml` exist for containerized runs.
- Run artifacts are written to `results_dir` (`~/.tradingagents/logs` by default): per-run report trees, `message_tool.log`, and `full_states_log_<date>.json`.

### Testing

- **75 test files, 428 `pytest.mark.unit` tests**, `pytest-subtests`, `--strict-markers -ra`. Markers: `unit`, `integration`, `smoke` (6 `integration` tests: 4 in `test_debate_gate.py`, 1 in `test_cli_display.py`, 1 live-API test in `test_deepseek_reasoning.py`).
- `tests/conftest.py` is the load-bearing piece: an **autouse fixture injects placeholder API keys for 14 providers** so a keyless CI cannot hang or silently skip, and a second autouse fixture **deep-copies `DEFAULT_CONFIG` around every test** because `set_config` merges and would otherwise leak vendor routing between tests.
- **Mocks over network**: 36 files use `monkeypatch`, 14 patch/mock. Vendor tests patch at the `requests`/client boundary.
- Tests are named behaviorally and reference issue numbers in comments (e.g. `test_unparseable_signal_is_review_not_silent_hold`), which doubles as a regression ledger.
- CI runs `pytest -q` on four Python versions, a **clean-install smoke job** that catches undeclared runtime deps (#994), and `ruff check .` over the full repo.

### Code style

- Ruff: `select = ["E","W","F","I","B","UP","C4","SIM"]`, `ignore = ["E501"]`, line length 100, target py310. `ruff format` adoption is deliberately deferred to avoid mass merge conflicts.
- `"**/__init__.py" = ["F401"]` — re-exports are intentional.
- Comments explain **why**, citing issue numbers (`#1170`, `#988`). This is unusually consistent and is the codebase's strongest convention. Docstrings state the contract and the failure mode.

## Signals / Active Considerations

Ordered by likely impact. These are planning inputs, not verdicts.

1. **`cli/main.py` is 1276 lines** and mixes Typer commands, Rich layout construction, streaming display, decorators, report saving, and selection prompts. It is still the largest file by ~1.8× and the clearest refactor target (`cli/utils.py` at 718 lines is second). Anything touching the CLI has a wide blast radius. The e02s02 extraction (`cli/gate_policy.py`, `cli/stream_handler.py`, `cli/complete_report.py`) took it down from 1460 lines without merging concerns into `cli/utils.py`.

2. **Graph-shape knowledge is duplicated in three places.** `trading_graph._run_signature()` builds the checkpoint signature from analysts/debate/risk/asset/portfolio/`gate=<debate_gate mode>`; `GraphSetup.setup_graph()` independently encodes the same shape as edges; `checkpointer.py` owns thread-ID construction. A change to pipeline shape must be mirrored correctly or checkpoints silently resume the wrong graph (#1089 guards this today via the signature, but the coupling remains).

3. **`GraphSetup.setup_graph()` hardcodes the analyst factory dict** (4 lambdas) while the node/clear/tool wiring is data-driven via `build_analyst_execution_plan`. Adding a 5th analyst requires editing the factory dict, the plan builder, and possibly `conditional_logic`. The abstraction is half-applied. The Debate Gate node (e02s01) is registered the same way: an explicit `add_node` plus the conditional entry edge from the last analyst, so the gate is a named node in the analyst→Research Manager path rather than part of the plan builder.

4. **No type gate.** Ruff enforces style and bugbear but nothing checks annotations. The Pydantic boundaries are safe; the internal graph/state plumbing (dict-shaped `AgentState`) is not. Adding `mypy` at any strictness would be a large, staged effort.

5. **Logging is unstructured and unconfigured.** Library modules log via stdlib but nothing sets a level, handler, or format, and there is no request/run correlation ID. Debugging a specific run means correlating by ticker+date inside `full_states_log_*.json`. `wire-observability` is the designed remedy.

6. **Single-vendor default in practice.** `data_vendors` defaults every category to `yfinance` except macro (`fred`) and prediction markets (`polymarket`). The fallback machinery is well-built but mostly dormant — a real multi-vendor chain (e.g. `yfinance,alpha_vantage`) is one config change and is untested in CI (only 1 integration test).

7. **The memory log is a flat markdown file** (`~/.tradingagents/memory/trading_memory.md`) with `memory_log_max_entries` defaulting to `None` (unbounded). Entry settlement depends on the holding window having traded, so it degrades gracefully but grows without limit.

8. **`review`/`REVIEW` is a first-class outcome with no automated follow-up.** A REVIEW signal is correctly not tradeable, but nothing retries or alerts — it surfaces only as a string in the CLI output and the saved report.

9. **Issue-number citations are the de facto decision record.** There is no `docs/adr/`; rationale lives in comments and in issue numbers that are not resolvable from this repo. `specs/adr/` is now scaffolded — backfilling the highest-value decisions (vendor taxonomy, structured-output fallback, rating integrity, checkpoint signature) is cheap and would preserve knowledge that currently dies with the issue tracker.

## Gaps this scan could not close

Recorded honestly rather than assumed:

- **Coverage percentage is unknown.** No coverage tool or threshold is configured; 428 unit tests over 12612 source lines is a size signal, not a quality one. `plan-tests` should establish a baseline before any large refactor.
- **The suite is timezone-dependent and CI cannot detect it.** CI runs `TZ=UTC`. Establishing the baseline on a `UTC+08:00` workstation surfaced 3 failures in `test_ohlcv_cache_freshness.py`, caused by pandas 3.0's naive `Timestamp.timestamp()` being UTC while `Timestamp.fromtimestamp()` is local. Fixed test-side (`specs/bugs/BUG-2026-09-20-ohlcv-cache-freshness-tz.md`), but any mtime/date arithmetic added later inherits the same blind spot until CI runs a non-UTC job.
- **No `docs/adr/`** — decisions must be reverse-engineered from comments and issue numbers, as noted in signal 9.
- **Real-provider behavior is unverified in CI.** All LLM and vendor tests mock at the boundary; nothing exercises a live provider, by design (no keys in CI).
