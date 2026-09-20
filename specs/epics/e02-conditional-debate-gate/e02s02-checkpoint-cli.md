# Story e02s02: Checkpoint policy keying + CLI surface

<!-- story: e02s02 -->

**type:** feat
**risk:** P1 (checkpoint resume correctness + user-visible display)
**context:** domain
**bcps:** 5
**status:** done (e45s06 ledger 6/6 passing; verified 9/9 phases, gate 100/100)

**Context:** e02s01 made the debate conditional at the library level. This story makes the
policy safe across **resumed** runs and visible to **interactive** users: the gate mode
joins the checkpoint run signature (#1089 pattern) so a resume can never continue a run
under a different gating policy, and the CLI grows a policy prompt step, a `skipped`
display status for Bull/Bear, and a Debate Gate section in run output and saved reports.

## Zoom-Out Check

| Module touched | Purpose | Callers | Contracts to preserve |
|---|---|---|---|
| `graph/trading_graph.py` `_run_signature` | Checkpoint-invalidating graph-shape inputs | `begin_checkpoint`, `clear_checkpoint_on_success` | Same signature ⇔ same graph behavior; a shape/policy change MUST produce a new thread ID |
| `cli/main.py` prompts + display | Interactive selection and live Rich display | `run_analysis` flow | Selections dict keys consumed by `_build_run_config`; env override precedence over interactive picks (existing research_depth pattern, `cli/main.py` ~L1029) |
| `cli/prefs.py` | Persisted user selections | CLI | Allowlist + sanitize round-trip; invalid values dropped |
| `tradingagents/reporting.py` `write_report_tree` | Saved report tree | `save_reports`, CLI | Report files render from `final_state` keys; absent data renders as an explicit note, never a blank |

## Requirements (delta tags, e45s29)

#### MODIFIED: Checkpoint run signature includes the gate policy
**Before:** `_run_signature` = analysts | debate rounds | risk rounds | asset | portfolio.
**After:** signature additionally carries `gate=<debate_gate mode>`; resuming a thread
created under a different mode starts fresh (no silent cross-policy resume).

#### ADDED: CLI gate-policy selection
Questionary step next to Research Depth: Auto (default, recommended) / Always / Never,
persisted via `cli/prefs.py` (allowlisted, sanitized), overridable by
`TRADINGAGENTS_DEBATE_GATE` with the same precedence + "(set by env)" notice as
research_depth.

#### ADDED: Skipped-debate visibility
Live display sets Bull/Bear to a `skipped` status when the stream shows the gate routed
to the Research Manager (no agent stuck at `pending`); the complete-report display and
`write_report_tree` render a **Debate Gate** section: skipped → verdict, direction,
confidence, rationale; held → "debate held (N turns)"; never → "disabled by
configuration". Gate decisions log at INFO, failures at WARNING (never silent).

## Slopcheck

No new external packages. `questionary`, `rich` **[OK]** — existing pinned dependencies.

## Steps

1. RED: extend `tests/test_checkpoint_lifecycle.py` — signature differs across gate modes; resume with changed mode starts fresh; same mode resumes (SC-e02s02-P1-01) → verify: `.venv/bin/python -m pytest -q tests/test_checkpoint_lifecycle.py -k gate --collect-only` (RED suite exists; tests fail until step 2 lands)
2. GREEN: add `f"gate={self.config.get('debate_gate', 'auto')}"` to `_run_signature` with a comment citing #1089 and this story → verify: `.venv/bin/python -m pytest -q tests/test_checkpoint_lifecycle.py tests/test_checkpoint_resume.py`
3. RED+GREEN CLI selection: gate-policy prompt step, prefs allowlist entry (`debate_gate` in `cli/prefs.py` with value validation), env precedence + env-skip notice (SC-e02s02-P1-02, P2-03) → verify: `.venv/bin/python -m pytest -q tests/test_cli_prefs.py tests/test_cli_config_precedence.py tests/test_cli_env_skip.py`
4. RED+GREEN display: `skipped` status path in the stream handler keyed on `debate_gate_verdict`; Bull/Bear never left `pending` on skip; analyst/wall-time logic untouched (SC-e02s02-P2-01) → verify: `.venv/bin/python -m pytest -q tests/test_cli_display.py`
5. RED+GREEN reports: Debate Gate section in `write_report_tree` output and the CLI complete-report display for all three modes (SC-e02s02-P2-02); INFO/WARNING logging assertions via caplog (SC-e02s02-P3-01) → verify: `.venv/bin/python -m pytest -q tests/test_debate_gate.py -k "report or logging"`
6. E2E CLI test with fake graph stream: auto-mode skip shows `skipped` and the gate section end to end → verify: `.venv/bin/python -m pytest -q tests/test_cli_display.py tests/test_debate_gate.py -k end_to_end`
7. Full Preflight → verify: `.venv/bin/python -m pytest -q && ruff check .`

## §17 Acceptance Criteria (Gherkin)

```gherkin
# scenario: SC-e02s02-P1-01
Given a checkpointed run completed the analyst phase under debate_gate="auto"
When the same ticker+date resumes under debate_gate="always"
Then the thread signature differs and the run starts fresh instead of resuming

# scenario: SC-e02s02-P1-02
Given TRADINGAGENTS_DEBATE_GATE="never" and a saved pref of "auto"
When the CLI builds the run config
Then debate_gate is "never" and the notice says it was set by the env var

# scenario: SC-e02s02-P2-01
Given an auto-mode run whose gate skips the debate
When the CLI streams the run
Then Bull and Bear show "skipped" and no research-team agent remains "pending"

# scenario: SC-e02s02-P2-02
Given any completed run
When the report tree is written
Then a Debate Gate section states skipped-with-rationale, held-with-turn-count, or disabled-by-configuration
```

## Verification Script (Step-by-Step, UAT)

1. `.venv/bin/python -m pytest -q tests/test_checkpoint_lifecycle.py tests/test_checkpoint_resume.py -v` — signature/resume scenarios pass.
2. `.venv/bin/python -m pytest -q tests/test_cli_prefs.py tests/test_cli_config_precedence.py tests/test_cli_env_skip.py tests/test_cli_display.py -v` — CLI scenarios pass.
3. Interactive (needs a provider key): run `python -m cli.main`, pick Auto at the new prompt, analyze a ticker with clearly aligned signals — observe the research team panel shows Bull/Bear as skipped and the final report contains the Debate Gate rationale.
4. Re-run with `TRADINGAGENTS_DEBATE_GATE=always` — observe the env notice replaces the prompt choice and the full debate runs.
5. `.venv/bin/python -m pytest -q && ruff check .` — Preflight green.

## Out of scope

- Docs/CHANGELOG/README (e02s03); risk-debate gating; dashboard/visual surfaces.

## Risks

- **Signature churn invalidating unrelated checkpoints** — the new `gate=` component
  changes every existing thread ID once on upgrade; acceptable (fresh start, no data
  loss) but must be stated in the e02s03 CHANGELOG entry.
- **CLI status vocabulary drift** — `skipped` is a new buffer status; display tests
  (SC-e02s02-P2-01) pin rendering before wiring.
- **Report rendering with absent verdict** (old states, `always` mode) — renders
  "debate held" from existing fields; blank-section regression guarded by SC-e02s02-P2-02.
