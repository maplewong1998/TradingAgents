# IMPACT — e02/e02s02 (checkpoint policy keying + CLI surface)

<!-- assess-impact --lightweight — build-epic step 2 pre-plan gate, 2026-09-20 -->
<!-- story: e02s02 -->

**Mode:** `--lightweight` (fan-in/fan-out + churn only; no coverage mapping).
**Baseline:** `main` @ `90d16be` (e02s01 landed as `d7557e4`).
**Verdict:** `Risk score 5 / 10` → below the 7 gate, **no `grill-me` session required**;
proceed to step 3 (`kickoff-branch`).

## Targets (MODIFIED — 4 existing modules, 0 new modules)

| Target | Contract that must be preserved |
|---|---|
| `tradingagents/graph/trading_graph.py::_run_signature` (:399-413) | Same signature ⇔ same graph behavior. Callers: `begin_checkpoint` (:454), `clear_checkpoint_on_success` (:500). |
| `cli/main.py` — prompts, stream-status handling, complete-report display | Selection dict keys consumed by `_build_run_config` (:1012); env precedence over interactive picks (#977 pattern, :1022-1035). |
| `cli/prefs.py` — `REMEMBERED` allowlist (:27-30) + `sanitize` (:62) | Round-trip of remembered answers; invalid values dropped, never raised. |
| `tradingagents/reporting.py::write_report_tree` (:13-101) | Report files render from `final_state` keys; absent data renders as an explicit note, never a blank. Callers: `cli/main.py:785`, `trading_graph.py:516` (`save_reports`). |

## Dependents (fan-in ≈ 8 production call sites)

- `trading_graph.py:454` (`begin_checkpoint`) and `:500` (`clear_checkpoint_on_success`) — `_run_signature`.
  The CLI stream path reaches the same code through `graph.begin_checkpoint(...)` (`cli/main.py:1176-1182`),
  which is why the signature is user-visible behavior, not just a library detail.
- `cli/main.py:1053` (`run_analysis`) → `_build_run_config`.
- `cli/main.py:502-503,609` → `load_last_run` / `save_last_run` / `sanitize`.
- `cli/main.py:785` and `trading_graph.py:516` → `write_report_tree`.
- `cli/main.py:1204,1219,1232` → `update_analyst_statuses` / `update_research_team_status` (internal).

Tests that already pin the touched surfaces: `tests/test_checkpoint_lifecycle.py:139`,
`tests/test_checkpoint_resume.py:195-215` (`test_run_signature_captures_graph_shape`),
`tests/test_portfolio_context.py:106-182`, `tests/test_reporting.py:23`,
`tests/test_cli_config_precedence.py` (6 call sites), `tests/test_cli_prefs.py` (8),
`tests/test_cli_env_skip.py`, `tests/test_cli_display.py`.

Churn (last ~6 commits per file): `trading_graph.py` 1 (`d7557e4`), `cli/main.py` 1 (`6398951`),
`reporting.py` 1 (`a0120e1`) — low, no hot-spot rework signal.

## Score inputs

| Factor | Points | Basis |
|---|---|---|
| Fan-in | 2 / 4 | ~8 production call sites across 4 modules; no shared public API widened |
| Fan-out | 2 / 3 | `cli/main.py` and `trading_graph.py` each depend on ~10 modules; `reporting.py` on none |
| Churn | 1 / 3 | 1 recent commit per target file |
| **Total** | **5 / 10** | below the 7 gate |

## Blast radius not captured by the fan-in count

1. **Checkpoint correctness is high-consequence, low-caller.** `_run_signature` has two callers, but a
   wrong value resumes a graph the run was not built for. This is the story's P1 scenario
   (SC-e02s02-P1-01) and the standing e02s01 gate requirement (IMPACT_LATEST.md:48, third encoding
   point) — **covered by frozen task 1**.
2. **`cli/main.py` is §File-Size-Exceptions capped at 1460 lines** (CONVENTIONS.md:244) under
   "these files MUST NOT grow further". All three CLI tasks (2, 3, 4-report-display) naturally land in
   that file; the e02s01 gate FAILED this exact rule once (`AUDIT-e02-e02s01.md:213-222`) and cleared it
   only by extraction. New CLI code therefore needs a home outside the capped files (e.g. a small
   `cli/*.py` module, following `cli/models.py` / `cli/stats_handler.py`), or an in-file extraction.
3. **`trading_graph.py` (651 lines, row 672) grows by one line** for `gate=` in the signature. Still
   under the frozen cap, but the row's literal wording is "MUST NOT grow further" — keep it to the
   single line.

## Affected stories

- **e02s01** (done) — supplies the mechanism the story keys on: `debate_gate` config + env mapping
  (`default_config.py:20,143`), `DebateGateVerdict`/markers (`agents/gate/schemas.py`),
  `AgentState.debate_gate_verdict` (`agent_states.py:73`), pre-initialization (`propagation.py:71-73`).
- **e02s02** (this story) — the four targets above.
- **e02s03** (docs) — must state the one-time signature churn (frozen e02s02 spec §Risks:98-100).
- **e02s03 / quick-fix** — the routed cosmetics that the frozen e02s02 tasks do **not** cover
  (see the drift list in `specs/state.yaml` handoff).

## Recommended action

Proceed. Add no new tests first — the frozen plan already pins every touched surface through
SC-e02s02-P1-01/P1-02/P2-01/P2-02/P2-03/P3-01. Two execution constraints carry into step 4:
do not grow `cli/main.py` past 1460, and keep the `trading_graph.py` delta to the single signature line.
