# Impact Analysis — TradingAgents

**Status:** ACTIVE — e02 assessment below (2026-09-20); base blast radius from `bigpowers init` scan.
**Produced by:** `assess-impact` → run **before** `plan-work` on any non-trivial change.

## Active assessment — e02 Conditional Bull/Bear Debate Gate (2026-09-20)

Modules touched, with callers and contracts from the Zoom-Out Check in
`specs/epics/e02-conditional-debate-gate/e02s01-gate-core-routing.md`:

| Module | Blast radius | Mitigation in plan |
|---|---|---|
| `graph/setup.py` (edge change) | 1 caller (`TradingAgentsGraph.__init__`); every run passes through the new node | SC-e02s01-P0-02 pins the `always`-mode node sequence to current main |
| `agents/managers/research_manager.py` (prompt variant) | graph node; output feeds Trader + rating extraction | SC-e02s01-P0-05 rating-integrity guard; held-debate prompt byte-identical |
| `graph/propagation.py` + `agents/utils/agent_states.py` (new field) | all state consumers; bare-state test paths | SC-e02s01-P1-04 pre-initialization test |
| `graph/trading_graph.py` `_run_signature` | checkpoint thread IDs — **all existing checkpoints re-key once** | SC-e02s02-P1-01; CHANGELOG announcement (e02s03) |
| `default_config.py` | every config consumer; env-override map | SC-e02s01-P1-02 validation tests |
| `cli/main.py`, `cli/prefs.py`, `reporting.py` | display + report rendering only | SC-e02s02-P2-01/02/03 with fake-buffer fixtures |

Untouched by design: `conditional_logic.should_continue_debate` (loop semantics unchanged
once Bull is entered), risk-debate nodes, vendor layer, llm_clients.
This assessment hits highest-risk classes 3 and 4 below (graph shape + AgentState fields).

## Pre-computed blast radius (from the `.codegraph` index, 2026-09-20)

Use these as a starting point; re-run `assess-impact` for the specific change.

| Symbol | Callers | Where |
|--------|---------|-------|
| `TradingAgentsGraph` | 37 | `cli/main.py`, `main.py`, `tradingagents/backtest.py`, `graph/__init__.py` |
| `create_llm_client` | 19 | `graph/trading_graph.py`, `llm_clients/__init__.py` |
| `TraderProposal` | 15 | `agents/trader/trader.py` |
| `VendorRateLimitError` | 11 | alpha_vantage_common, interface, sec_edgar, stockstats_utils, y_finance |
| `invoke_structured_or_freetext` | 9 | sentiment_analyst, portfolio_manager, research_manager, trader |
| `BaseLLMClient` | 8 | all `llm_clients/*` implementations |
| `bind_structured` | 8 | sentiment_analyst, portfolio_manager, research_manager, trader |
| `process_signal` | 7 | CLI + graph |
| `VendorNotConfiguredError` | 6 | alpha_vantage_common, fred, interface |
| `VendorError` | 4 | alpha_vantage_indicator, y_finance |
| `GraphSetup` | 3 | `graph/__init__.py`, `trading_graph.py` |
| `propagate` | 2 | `backtest.py` |
| `setup_graph` | 1 | `trading_graph.py` |

## Highest-risk change classes

1. **Touching `dataflows/errors.py` or `interface.route_to_vendor`** — every vendor path and every analyst's tools flow through it. Additive subclassing is cheap; changing the taxonomy is not.
2. **Touching `agents/utils/rating.py`** — four consumers must agree. A change here can silently desynchronize the signal from the memory log (`test_rating_integrity.py` guards this).
3. **Changing graph shape** (analyst set, debate depth, node names) — must be mirrored into `_run_signature`, `setup_graph`, and `DEBATE_PATH_MAP`/`RISK_ANALYSIS_PATH_MAP`, or checkpoints resume the wrong graph.
4. **Changing `AgentState` fields** — every node reads it untyped; nothing catches a renamed key at build time.
5. **Restructuring `cli/`** — `cli/main.py` at 1460 lines with 67 `console.print(...)` calls across the package; `test_cli_*.py` is the only safety net.
