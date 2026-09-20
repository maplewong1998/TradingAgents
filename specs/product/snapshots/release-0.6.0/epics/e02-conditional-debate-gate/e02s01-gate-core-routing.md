# Story e02s01: Tracer bullet — gate node routes aligned runs past the debate

<!-- story: e02s01 -->

**type:** feat
**risk:** P0 (decision-path routing; test-plan P0 scenarios live here)
**context:** domain
**bcps:** 8
**status:** failing (e45s06 ledger — flips per task as verify exits 0)

**Context:** The Bull/Bear investment debate runs on every analysis even when the four
analyst reports agree, burning `2 × max_debate_rounds` full LLM calls re-arguing a settled
question. This story inserts a **Debate Gate** node between the analyst phase and the
debate: an LLM judge (quick model, structured output) decides whether genuine tension
exists, and routes via LangGraph `Command` either into the debate or straight to the
Research Manager. Skipping is conservative — only clear alignment with adequate
confidence skips; any failure falls back to the debate. Policy is configurable
(`debate_gate: always|auto|never`, default `auto`). Confirmed design decisions:
grill-with-docs 2026-09-20; evidence base: `specs/product/SCOPE_LATEST.yaml` § Prior Art.

## Zoom-Out Check

| Module touched | Purpose | Callers | Contracts to preserve |
|---|---|---|---|
| `graph/setup.py` `GraphSetup.setup_graph` | Compile the agent StateGraph | `TradingAgentsGraph.__init__` (sole) | Every node named in a path map / Command target is registered; START → first analyst; debate-loop edges unchanged |
| `graph/conditional_logic.py` | Route debate/risk loops | graph edges | `should_continue_debate` semantics untouched — it still governs the loop once Bull is entered |
| `agents/managers/research_manager.py` | Debate → investment plan | graph node | Returns `investment_debate_state` + `investment_plan`; output always carries a parseable 5-tier rating (#1170) |
| `graph/propagation.py` | Initial state | `TradingAgentsGraph.create_run_state` | Every `AgentState` field pre-initialized (house rule) |
| `default_config.py` | Config + env overrides | graph, CLI, dataflows | `DEFAULT_CONFIG` complete; env-override map pattern preserved |
| `agents/schemas.py` | Typed agent outputs | agents | Pydantic models + render helpers; docstrings state contract and failure mode |

## Requirements (delta tags, e45s29)

#### ADDED: Typed debate-gate verdict
`DebateGateVerdict` schema: `evidence_aligned: bool`, `confidence: low|medium|high`,
`aligned_direction: bullish|bearish|mixed|unclear|None`, `rationale: str`, plus
`render_debate_gate_marker(verdict)` producing the downstream skip marker.

#### ADDED: Debate Gate agent
`create_debate_gate(quick_llm)` factory (new `tradingagents/agents/gate/` package).
**Reason for Depth:** isolates policy-routing agents from evidence-producing agents, and
the same factory shape will serve the deferred risk-debate gate without re-plumbing.
Judges the four reports (via `report_or_absent`) with `bind_structured`; returns
`Command[Literal["Bull Researcher", "Research Manager"]]` whose `update` records the
rendered verdict. Reads the policy from `get_config()["debate_gate"]` at invocation
(house pattern, cf. `get_language_instruction`).

#### ADDED: debate_gate configuration
`debate_gate: "auto"` in `DEFAULT_CONFIG`; `TRADINGAGENTS_DEBATE_GATE` env override;
unknown values raise a clear `ValueError` (valid set in the message) at graph init,
before any analyst spend.

#### MODIFIED: Analyst phase hands off to the debate
**Before:** last analyst's `Msg Clear` node has an unconditional edge to `Bull Researcher`;
the debate always runs.
**After:** that edge targets `Debate Gate`; the gate routes to `Bull Researcher`
(tension / ambiguity / thin evidence / gate failure / `always`) or to `Research Manager`
(aligned+confident under `auto`; any verdict under `never`).

#### MODIFIED: Research Manager handles a skipped debate
**Before:** RM prompt interpolates the debate history and asserts "The debate always
contains conflicting arguments"; an empty history invites fabrication (#1176 class).
**After:** on skip, `investment_debate_state.history` carries the explicit alignment
marker and the RM prompt swaps the conflict paragraph for an uncontested-evidence
instruction (commit to a 5-tier rating from the aligned reports; do not fabricate
conflict; do not drift to Hold). Held-debate prompt text is unchanged.

#### ADDED: Gate state field
`AgentState.debate_gate_verdict: str` ("" when the debate ran), initialized in
`create_initial_state`; the audit trail for CLI/report surfaces in e02s02.

## Discovery Mandate (external API, verified)

LangGraph `Command` routing — verified by direct import on installed langgraph 1.2.11:
`from langgraph.types import Command` → `<class 'langgraph.types.Command'>`;
`StateGraph.add_conditional_edges(source, path, path_map=None)`. Official judge-node
pattern (structured call → `Command(update=..., goto=...)`):
https://docs.langchain.com/oss/python/langgraph/thinking-in-langgraph. pyproject floor
`langgraph>=0.4.8` already provides `Command` — **no dependency change**.

## Slopcheck

No new external packages. `langgraph` **[OK]** — existing pinned dependency, Command API
verified in the installed version. `pydantic` **[OK]** — existing (schemas.py pattern).

## Steps

1. RED: create `tests/test_debate_gate.py` (`# story: e02s01`) covering SC-e02s01-P0-01/03/04/05, P1-01/02/03/04/05, P2-01 — verdict schema, marker text, gate routing matrix (aligned+confident → RM; conflicted / mixed-direction / low-confidence → Bull; exception/None → Bull + WARNING log), always/never zero-LLM-call paths, initial-state field, RM prompt variants, non-English reports → verify: `.venv/bin/python -m pytest -q tests/test_debate_gate.py --collect-only` (RED suite exists and parses; the tests themselves fail until tasks 2–8 land)
2. GREEN schema: add `DebateGateVerdict` + `render_debate_gate_marker` to `agents/schemas.py` following the `SentimentReport` pattern (Literals, contract+failure-mode docstring) → verify: `.venv/bin/python -m pytest -q tests/test_debate_gate.py -k "schema or marker"`
3. GREEN gate agent: new `tradingagents/agents/gate/{__init__,debate_gate}.py` with `create_debate_gate(llm)`; export from `agents/__init__.py`; judge prompt built from the four `report_or_absent` reports + instrument context; `bind_structured`; `Command[Literal["Bull Researcher","Research Manager"]]`; fail-safe (exception/None → Bull + `logger.warning`); policy short-circuits before any LLM call → verify: `.venv/bin/python -m pytest -q tests/test_debate_gate.py -k gate`
4. State: add `debate_gate_verdict` to `AgentState` + `Propagator.create_initial_state` → verify: `.venv/bin/python -m pytest -q tests/test_debate_gate.py -k initial_state`
5. Wiring: register `"Debate Gate"` node in `GraphSetup.setup_graph`; replace the last-analyst-clear → `"Bull Researcher"` edge with → `"Debate Gate"`; comment cites #1088 (targets statically compiled) → verify: `.venv/bin/python -m pytest -q tests/test_debate_gate.py -k graph && .venv/bin/python -m pytest -q tests/test_risk_router_path_map.py`
6. RM prompt: conditional paragraph keyed on `state["debate_gate_verdict"]`; held-debate text byte-identical to today → verify: `.venv/bin/python -m pytest -q tests/test_structured_agent_prompts.py tests/test_debate_gate.py -k research_manager`
7. Config: `debate_gate: "auto"` + `TRADINGAGENTS_DEBATE_GATE` in `default_config.py`; validation at `TradingAgentsGraph.__init__` (clear ValueError) → verify: `.venv/bin/python -m pytest -q tests/test_env_overrides.py tests/test_debate_gate.py -k config`
8. Graph-level E2E with stubbed agents: SC-e02s01-P0-02 (always ⇒ node-visit sequence identical to current main), SC-e02s01-P0-04/05 (skip ⇒ marker in RM input, `process_signal` yields a 5-tier rating, Bull/Bear never invoked) → verify: `.venv/bin/python -m pytest -q tests/test_debate_gate.py -k "node_sequence or end_to_end"`
9. Full Preflight + consistency → verify: `.venv/bin/python -m pytest -q && ruff check .`

## §17 Acceptance Criteria (Gherkin — scenario IDs per e02-TEST_PLAN_LATEST.md)

```gherkin
# scenario: SC-e02s01-P0-01
Given debate_gate is "auto" and the gate's structured call raises
When the graph runs the analyst phase
Then the Bull Researcher is invoked and a WARNING is logged and debate_gate_verdict records the failure

# scenario: SC-e02s01-P0-02
Given debate_gate is "always"
When the graph runs
Then the visited-node sequence equals the current unconditional-debate sequence and the gate made zero LLM calls

# scenario: SC-e02s01-P0-03
Given the judge returns evidence_aligned=false or confidence="low"
When the gate runs
Then it routes to "Bull Researcher"

# scenario: SC-e02s01-P0-04
Given the judge returns evidence_aligned=true with confidence!="low"
When the gate runs
Then it routes to "Research Manager" and investment_debate_state.history is the explicit alignment marker, never empty

# scenario: SC-e02s01-P0-05
Given a skipped debate
When the RM produces its plan
Then process_signal extracts one of Buy/Overweight/Hold/Underweight/Sell (not REVIEW)

# scenario: SC-e02s01-P1-02
Given TRADINGAGENTS_DEBATE_GATE="bogus"
When the graph is constructed
Then a ValueError naming the valid modes is raised
```
(SC-e02s01-P1-01/03/04/05, P2-01 covered by unit tests tagged with the same IDs.)

## Verification Script (Step-by-Step, UAT)

1. Run `.venv/bin/python -m pytest -q tests/test_debate_gate.py -v` — observe all gate scenarios pass.
2. Run `.venv/bin/python -m pytest -q` — observe the full suite green (no regression in `test_structured_agent_prompts.py`, `test_risk_router_path_map.py`).
3. Run `ruff check .` — observe "All checks passed!".
4. Offline smoke: `TRADINGAGENTS_DEBATE_GATE=bogus .venv/bin/python -c "from tradingagents.default_config import DEFAULT_CONFIG; from tradingagents.graph.trading_graph import TradingAgentsGraph; TradingAgentsGraph(config=DEFAULT_CONFIG)"` — observe a clear ValueError naming always/auto/never.

## Out of scope

- Checkpoint run-signature keying and CLI surface (e02s02); docs (e02s03).
- Risk-debate gating; scored tension thresholds; structured output for other analysts
  (SCOPE_LATEST out_of_scope #1–3).

## Risks

- **RM rating drift on skipped path** (Hold-bias when no conflict presented) — detected by
  SC-e02s01-P0-05; mitigated by explicit "commit to a rating" instruction.
- **Command-target drift crashing mid-run** (#1088 class) — mitigated by typed
  `Command[Literal[...]]` + compile-time target registration test (SC-e02s01-P1-01).
- **Judge prompt-quality variance across providers** — out of test scope (model behavior);
  fail-safe routing bounds the damage (SC-e02s01-P0-01).
- **Default-behavior change surprising users** — announced in e02s03; `always` restores
  exact prior behavior (SC-e02s01-P0-02 guards it).
