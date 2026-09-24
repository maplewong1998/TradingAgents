# Story e03s06: Signal-family trigger states tool (get_signal_states)

<!-- story: e03s06 -->

**type:** feat
**risk:** P1 (new read-only tool over versioned PIT signals)
**context:** domain
**bcps:** 3
**status:** planned (e45s06 ledger — tasks start `failing`, flip only on green verify)

**Context:** Augury's `/api/v1/signals/{ticker}` serves versioned,
point-in-time trigger states for its signal families — seven technical families
(`sma_streak`, `sma_cross`, `rsi_cross`, `macd_cross`, `bb_cross`,
`adx_breakout`, `psar_flip`) plus knowledge families (`hurst`, `regime`,
`sentiment`, `insider`, `earnings_surprise`, `quality`) from the lake's
`signals/registry.py`. Because `family` and `as_of` are both required upstream,
this endpoint is fully PIT-safe for backtests — the one augury-only surface
with no live-vintage caveat. This story exposes it as `get_signal_states`,
bound to the market and fundamentals analysts under the e03s05 binding gate.

## Zoom-Out Check

| Module touched | Purpose | Callers | Contracts to preserve |
|---|---|---|---|
| `dataflows/augury.py` | Augury lake HTTP vendor | `route_to_vendor` | `get_augury_signal_states(ticker, family, curr_date)`; unknown family surfaces the valid set, never a stack trace |
| `dataflows/interface.py` | The only vendor seam | `@tool` wrappers | New category `signal_states` in `TOOLS_CATEGORIES` + `OPTIONAL_CATEGORIES`; registration-only |
| `agents/utils/signal_states_tools.py` (NEW) | `@tool` wrapper | analysts, `agent_utils.__all__` | `InjectedState("trade_date")` + `as_of` clamp pattern |
| `graph/trading_graph.py` `_create_tool_nodes` | Per-analyst ToolNodes | `TradingAgentsGraph.__init__` | Same binding gate as e03s05; default config binds nothing |

## Requirements (delta tags, e45s29)

#### ADDED: get_signal_states tool
`@tool get_signal_states(ticker, family, curr_date)` → `GET
/api/v1/signals/{ticker}?family=<family>&as_of=<clamped curr_date>` (both
required upstream), optional `version=vYYYYMMDD` pin left to a later story.
The tool's `family` argument description enumerates the valid families; the
vendor maps a 422/unknown-family response to a helpful message listing the
valid set (a bad LLM-supplied family is a *caller's* miss, and the category is
optional — the run must continue). Renders each family's trigger state
(`triggered` + preset detail, per the lake registry contract) with the signal
date and version shown so staleness is visible.

#### ADDED: Analyst bindings
Bound to the market analyst (technical families) and the fundamentals analyst
(knowledge families) — one tool, both nodes, gated by the `signal_states`
category configuration. Prompt paragraphs name the families each analyst
should care about.

## Discovery Mandate (external API, verified)

Verified 2026-09-24 against `~/Repo_Private/augury/openapi.json` +
`src/augury_record/signals/registry.py`: `GET /api/v1/signals/{ticker}` params
`ticker*`, `family*`, `as_of*`, `version`, `fields`, `page`, `page_size`;
response codes 200/404/422. Registry docstring: "Signal family registry —
single source of truth for the 7 technical families", `SIGNAL_FAMILIES`
frozenset + knowledge families (e12s03), `compute_technicals` returns "the
last-row trigger state for one family — `triggered` is whether the family's
boolean condition fired"; unknown family raises `KeyError` lake-side. Signal
definitions are SCD2-versioned (`daily_features.py:188-202`, M33).

## Slopcheck

No new external packages. `requests` **[OK]** — via the e03s01 `_request` helper.

## Steps

1. RED: extend `tests/test_augury_tools.py` (`# story: e03s06`) — trigger-state
   markdown (triggered + detail + signal date + version), unknown family →
   message listing the valid set with no abort, as_of forwarded as the clamped
   trade date, binding-gate on/off for both analysts → verify: `.venv/bin/python -m pytest -q tests/test_augury_tools.py -k signal --collect-only`
2. GREEN vendor `get_augury_signal_states` + the valid-family vocabulary
   constant (comment cites `signals/registry.py`) → verify: `.venv/bin/python -m pytest -q tests/test_augury_tools.py -k "signal and vendor"`
3. Seam: `signal_states` category in `TOOLS_CATEGORIES` + `VENDOR_METHODS` +
   `OPTIONAL_CATEGORIES` → verify: `.venv/bin/python -m pytest -q tests/test_augury_tools.py -k "registration or routing"`
4. GREEN tool + bindings: `signal_states_tools.py`, `agent_utils.__all__`
   export, market + fundamentals binding-gate appends and conditional prompt
   paragraphs → verify: `.venv/bin/python -m pytest -q tests/test_augury_tools.py -k "signal and (tool or binding or prompt)"`
5. Full Preflight → verify: `.venv/bin/python -m pytest -q && ruff check .`

## §17 Acceptance Criteria (Gherkin)

```gherkin
# scenario: SC-e03s06-P1-01
Given signal_states configured as "augury"
When the market analyst calls get_signal_states("0700.HK", "rsi_cross", "2026-09-20")
Then the markdown shows the family's triggered state, detail, signal date, and version

# scenario: SC-e03s06-P1-02
Given the same configuration
When the analyst calls get_signal_states with family "momentum_magic"
Then the reply lists the valid families and the run continues

# scenario: SC-e03s06-P1-03
Given a stock default_config
When the analyst ToolNodes are built
Then get_signal_states is bound nowhere and prompts are unchanged
```

## Verification Script (Step-by-Step, UAT)

1. Run `.venv/bin/python -m pytest -q tests/test_augury_tools.py -v -k signal` — all green.
2. Run `.venv/bin/python -m pytest -q` and `ruff check .` — full Preflight green.
3. Optional live smoke: with the lake up and `signal_states: "augury"`, ask for
   the `regime` family on a covered ticker and observe the versioned trigger
   state in the market report.

## Out of scope

- Vintage pinning UX (`version=vYYYYMMDD` stays an API param, not a tool
  argument); lake-side family additions (registry is the lake's SoT — the TA
  vocabulary constant is pinned by tests); cross-sectional signals (e03s07).

## Risks

- **Family vocabulary drift between repos** — the valid-set constant is pinned
  by tests; drift fails the suite, and the unknown-family path degrades
  gracefully in production.
- **SCD2 version confusion** (same family, changed formula) — the rendered
  markdown always shows the version, so two runs are comparable by eye.
- **Duplicate binding across two analysts** — intended: one tool, two nodes;
  the gate predicate is shared so both flip together.
