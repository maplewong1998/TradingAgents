---
feature: "e02 — Conditional Bull/Bear Debate Gate"
epic_id: e02
stories: [e02s01, e02s02, e02s03]
phase: "5 (project-level VERIFY, off-main)"
skill: run-evals
owner: "resident project-level run-evals child"
graded_at: "2026-09-20T10:52:09Z"
repo: /home/maplewong1998/Repository/TradingAgents
worktree: "none — graded at the repository root on `main`"
tip: dc9c5c1
feature_tip: b883f43
tip_note: "`git diff --stat b883f43..dc9c5c1` = progress.md + specs/state.yaml + specs/fleet-agents.yaml only (orchestrator Phase-5 bookkeeping). No product, test or doc file changed, so the graded tree is the delivered e02 tree."
mode: "read-only judge — no file inside the repo was created or modified; eval artefact and scratch under /tmp/phase5-evals-e02/"
env: ".venv/bin/python 3.12.11 (repo-root virtualenv), PYTHONDONTWRITEBYTECODE=1, pytest -q -p no:cacheprovider"
suite_scope: "targeted pytest node ids at the repo root; the whole-suite Preflight leg is delegated (see § Delegated legs)"
k: 1
k_note: "every grader here is a deterministic code grader (pytest node id or shell gate), so pass@1 is the whole estimate; no model grader and no stochastic grader in this set, so no repeat-k promotion is possible"
evals_total: 33
evals_passing: 33
evals_flaky: 0
pytest_node_executions: 327
test_files_touched: 17
scenarios_in_test_plan: 18
scenarios_with_a_runnable_grader: 18
overall_verdict: pass
---

# EVALS — e02 Conditional Bull/Bear Debate Gate (Phase 5 run-evals)

Epic e02 landed on `main` at `b883f43` (three stories: e02s01 gate core routing,
e02s02 checkpoint policy keying + CLI surface, e02s03 docs + knowledge). This is the
project-level, post-landing eval set for the delivered feature: it names the capability,
formalises the graders, runs them serially in the root `.venv`, and records the observed
result per eval.

Scenario basis: `specs/tech-architecture/e02-TEST_PLAN_LATEST.md` (SC-e02s01-P0-01..05,
P1-01..05, P2-01; SC-e02s02-P1-01, P1-02, P2-01..03, P3-01; SC-e02s03-P2-01, P3-01 — 18
scenarios) plus the three stories' §17 Gherkin in
`specs/epics/e02-conditional-debate-gate/`.

Command form used for every pytest grader below (`<node>` = one or more node ids):

```bash
cd /home/maplewong1998/Repository/TradingAgents
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider <node>
```

`-p no:cacheprovider` + `PYTHONDONTWRITEBYTECODE=1` are the read-only flags: they keep
`.pytest_cache`/`__pycache__` writes out of the repo. Raw serial-run log:
`/tmp/phase5-evals-e02/results.txt`.

## 1. Capability evals — does the feature do its job?

| ID | Evals (one sentence) | Covers | Grader (code) | Tier | Result |
|---|---|---|---|---|---|
| C-01 | Aligned + confident + directional verdict routes **past** the debate into the Research Manager | SC-e02s01-P0-04 | `test_debate_gate.py::test_aligned_and_confident_routes_past_the_debate` + `::test_aligned_above_low_confidence_with_a_direction_routes_past_the_debate` (4 params) | ALWAYS_PASSES | PASS (5 passed) |
| C-02 | Conflicted / low-confidence / mixed / unclear / no-direction verdicts all **hold** the debate | SC-e02s01-P0-03 | `test_debate_gate.py::test_tension_or_ambiguity_routes_to_the_debate` (6 params) | ALWAYS_PASSES | PASS (6 passed) |
| C-03 | A judge that raises, returns `None` or returns an unparseable payload is fail-safe: debate held, WARNING logged, verdict records the failure, **no free-text retry** | SC-e02s01-P0-01 | `test_debate_gate.py::{test_gate_exception_is_fail_safe_and_logged, test_unparseable_gate_result_routes_to_the_debate, test_a_failed_gate_does_not_retry_as_free_text, test_gate_failure_end_to_end_falls_back_to_the_debate}` | ALWAYS_PASSES | PASS (4 passed) |
| C-04 | `always` ⇒ full debate with **zero** judge calls and the unconditional node sequence; `never` ⇒ policy skip with the policy marker and zero judge calls | SC-e02s01-P0-02, SC-e02s01-P1-05 | `test_debate_gate.py::{test_always_policy_runs_the_debate_without_asking_the_judge, test_never_policy_skips_without_asking_the_judge, test_never_policy_marker_does_not_claim_a_judge_alignment_finding, test_node_sequence_with_always_matches_the_unconditional_debate, test_node_sequence_skip_never_invokes_the_debaters}` | ALWAYS_PASSES | PASS (5 passed) |
| C-05 | A skip hands the RM a **non-empty** alignment marker (never an empty transcript); the skipped-debate RM prompt exists only on the skip and the held prompt is unchanged; both skip paths still yield a 5-tier rating | SC-e02s01-P0-04, P0-05, P1-03 | `test_debate_gate.py::{test_marker_is_never_empty_so_a_missing_transcript_cannot_read_as_empty, test_research_manager_skipped_debate_prompt_states_uncontested_evidence, test_research_manager_held_debate_prompt_is_unchanged, test_research_manager_skip_path_still_yields_a_five_tier_rating, test_research_manager_skip_path_prompt_tells_the_model_what_to_do, test_skip_path_process_signal_is_a_five_tier_rating, test_policy_skip_reaches_the_rm_with_a_marker_and_a_five_tier_rating}` | ALWAYS_PASSES | PASS (7 passed) |
| C-06 | `Command` targets are statically typed and registered nodes — a drifted label cannot crash mid-run | SC-e02s01-P1-01 | `test_debate_gate.py::{test_gate_command_targets_are_registered_graph_nodes, test_gate_declares_its_targets_as_a_literal_union, test_graph_compiles_with_the_gate_node_registered}` | ALWAYS_PASSES | PASS (3 passed) |
| C-07 | `debate_gate` config validates (bogus value ⇒ clear error naming the valid set, at env read and at graph init), `TRADINGAGENTS_DEBATE_GATE` overrides the default, default ships `auto`, unknown/missing policy never skips | SC-e02s01-P1-02 | `test_debate_gate.py::{test_debate_gate_config_is_env_overridable (3 params), test_debate_gate_config_rejects_a_bogus_env_value, test_config_validation_rejects_a_bogus_mode_at_graph_init, test_default_config_ships_debate_gate_auto, test_the_two_valid_mode_lists_stay_in_sync, test_missing_policy_falls_back_to_auto, test_unknown_policy_never_skips_the_debate}` | ALWAYS_PASSES | PASS (9 passed) |
| C-08 | `create_initial_state` pre-initialises the gate field; the judge sees all four reports; the policy is read at invocation, not factory build (bare programmatic states never KeyError) | SC-e02s01-P1-04 | `test_debate_gate.py::{test_create_initial_state_pre_initializes_the_gate_verdict, test_agent_state_declares_the_gate_verdict_field, test_the_judge_sees_all_four_reports_and_an_absent_marker, test_policy_is_read_at_invocation_not_at_factory_build}` | ALWAYS_PASSES | PASS (4 passed) |
| C-09 | Language independence: non-English analyst reports gate identically | SC-e02s01-P2-01 | `test_debate_gate.py::test_non_english_reports_route_identically` | ALWAYS_PASSES | PASS (1 passed) |
| C-10 | Checkpoint re-key: `_run_signature` carries `gate=<mode>`; a resume under a **changed** mode starts fresh, the **same** mode resumes | SC-e02s02-P1-01 | `test_checkpoint_lifecycle.py::{test_the_run_signature_carries_the_gate_mode, test_a_resume_under_a_changed_gate_mode_starts_fresh, test_the_same_gate_mode_still_resumes}` | ALWAYS_PASSES | PASS (3 passed) |
| C-11 | CLI gate-policy prompt step; prefs remember + sanitize; env beats the menu pick; the env override is announced **once** | SC-e02s02-P1-02, SC-e02s02-P2-03 | `test_cli_prefs.py::{test_the_debate_gate_policy_is_remembered_only_while_it_is_choosable, test_a_remembered_gate_policy_prefills_the_menu, test_a_gate_policy_is_asked_for_and_remembered_after_a_run}` + `test_cli_config_precedence.py::{test_env_debate_gate_wins_over_the_prompt_choice_and_says_so, test_the_gate_choice_reaches_the_config_without_env}` + `test_cli_env_skip.py::{TestDebateGateSkippedFromEnv::test_gate_env_skips_the_policy_prompt, TestDebateGateEnvNotice::test_env_policy_short_circuits_the_menu_without_announcing_itself, TestDebateGateEnvNotice::test_the_env_notice_is_printed_once_across_the_run}` | ALWAYS_PASSES | PASS (8 passed) |
| C-12 | Live display on skip: Bull/Bear read `skipped` (no agent left `pending`), the status survives the RM decision, and a held debate is not misread as skipped | SC-e02s02-P2-01 | `test_cli_display.py::{test_a_skipped_debate_leaves_no_research_agent_pending, test_skipped_survives_the_research_manager_decision, test_a_held_debate_is_not_read_as_skipped, test_the_progress_panel_renders_the_skipped_status}` | ALWAYS_PASSES | PASS (4 passed) |
| C-13 | Report surface: the **Debate Gate** section renders skipped-with-rationale, held-in-N-turns and skipped-by-configuration, is omitted when nothing was recorded, and reaches the on-screen complete report | SC-e02s02-P2-02 | `test_debate_gate.py::{test_report_tree_states_a_skipped_debate_with_its_rationale, test_report_tree_counts_a_held_debate_in_turns, test_report_tree_names_a_configuration_skip, test_report_tree_omits_the_gate_section_when_nothing_was_recorded, test_the_complete_report_display_carries_the_gate_section}` | ALWAYS_PASSES | PASS (5 passed) |
| C-14 | E2E: one auto-mode run decided by the real gate node, driven through the real per-chunk CLI handler, ends with Bull/Bear `skipped`, the gate section in the saved tree and on screen | SC-e02s02-P2-01, P2-02 (E2E) | `test_cli_display.py::test_the_cli_stream_end_to_end_shows_a_skip_and_the_gate_section` | ALWAYS_PASSES | PASS (1 passed) |
| C-15 | Gate verdict + rationale log at INFO with the ticker in the record; the failure path logs WARNING with the ticker | SC-e02s02-P3-01 | `test_debate_gate.py::{test_gate_logging_names_the_ticker_and_the_rationale_on_a_skip, test_gate_logging_names_the_ticker_on_a_policy_skip, test_gate_logging_warning_still_names_the_ticker_on_failure}` | ALWAYS_PASSES | PASS (3 passed) |
| C-16 | Docs: the CHANGELOG states the default change, the one-time checkpoint re-keying, the exact `always` restore switch and the fail-safe direction | SC-e02s03-P2-01 | `bash /tmp/phase5-evals-e02/g16-changelog.sh` (6 greps, below) | ALWAYS_PASSES | PASS |
| C-17 | Docs: `.env.example` documents `TRADINGAGENTS_DEBATE_GATE` + the default and the mode meanings; README documents `debate_gate`, the CLI step, the skip and the fail-safe paragraph | SC-e02s03-P2-01 | `bash /tmp/phase5-evals-e02/g17-env-readme.sh` (8 greps, below) | ALWAYS_PASSES | PASS |
| C-18 | Knowledge refresh: `tech-stack.md` flow + signature note carry the Debate Gate; the glossary defines **Debate Gate**, **Alignment Marker**, **debate_gate policy** with code sources | SC-e02s03-P3-01 | `bash /tmp/phase5-evals-e02/g18-knowledge.sh` (6 greps, below) | ALWAYS_PASSES | PASS |
| C-19 | House cap discipline: the three new CLI modules are ≤300 lines and absent from CONVENTIONS § File-Size Exceptions, and every recorded exception row still matches the real line count | (house convention, no SC id) | `bash /tmp/phase5-evals-e02/g19-conventions-caps.sh` | ALWAYS_PASSES | PASS (after 1 grader repair, see § Grader repairs) |
| C-20 | The gate skip cannot disturb analyst status bookkeeping or the analyst wall-time tracker (`stream_handler` reuses the chunk-sync path) | SC-e02s02-P2-01 (second half) | `test_analyst_execution.py` (whole file, 7 nodes) + `test_cli_display.py::test_a_skipped_debate_leaves_no_research_agent_pending` | ALWAYS_PASSES | PASS (8 passed) |

### Doc / shell grader bodies (C-16, C-17, C-18)

```bash
# C-16 — run from the repo root
grep -qi 'debate becomes conditional' CHANGELOG.md
grep -qi 'held only when the evidence is contested' CHANGELOG.md
grep -q  'One-time checkpoint re-keying (`gate=<mode>`)' CHANGELOG.md
grep -qi 'restore switch is exact' CHANGELOG.md
grep -q  'TRADINGAGENTS_DEBATE_GATE' CHANGELOG.md
grep -qi 'a gate that cannot judge holds the debate' CHANGELOG.md

# C-17
grep -q 'TRADINGAGENTS_DEBATE_GATE=auto' .env.example
grep -qi 'always holds the debate on every run' .env.example
grep -qi 'never holds no debate' .env.example
grep -q 'config\["debate_gate"\] = "auto"' README.md
grep -q 'TRADINGAGENTS_DEBATE_GATE=always' README.md
grep -qi 'Debate Gate Policy' README.md
grep -qi 'Fail-safe' README.md
grep -qi 'skipped' README.md

# C-18
grep -q 'Debate Gate' specs/tech-architecture/tech-stack.md
grep -q 'gate=<debate_gate mode>' specs/tech-architecture/tech-stack.md
grep -q 'term: Debate Gate' specs/product/GLOSSARY_LATEST.yaml
grep -q 'term: Alignment Marker' specs/product/GLOSSARY_LATEST.yaml
grep -q 'term: debate_gate policy' specs/product/GLOSSARY_LATEST.yaml
grep -q 'tradingagents/agents/gate/debate_gate.py' specs/product/GLOSSARY_LATEST.yaml
```

## 2. Regression evals — did we break anything?

| ID | Evals (one sentence) | Grader (code) | Tier | Result |
|---|---|---|---|---|
| R-01 | Preflight **lint** leg: `ruff check .` clean | `.venv/bin/python -m ruff check .` | ALWAYS_PASSES | PASS — `All checks passed!` |
| R-02 | e01 invariant subset: rating integrity + signal processing + vendor seam (`route_to_vendor`, `VendorError` taxonomy) intact | `test_rating_integrity.py` + `test_signal_processing.py` + `test_vendor_routing.py` + `test_vendor_errors.py` | ALWAYS_PASSES | PASS (50 passed) |
| R-03 | e02s01 routing-matrix + fail-safe slice of the gate suite (the skip-caution contract) | `test_debate_gate.py -k "routes_to_the_debate or routes_past_the_debate or policy or node_sequence or process_signal or fail_safe or unparseable"` | ALWAYS_PASSES | PASS (24 passed, 40 deselected) |
| R-04 | Checkpoint lifecycle + resume invariants across the **whole** files (not just the gate nodes) | `test_checkpoint_lifecycle.py` + `test_checkpoint_resume.py` | ALWAYS_PASSES | PASS (15 passed) |
| R-05 | Held-debate prompt unchanged + structured-agent contract (`test_structured_agent_prompts.py` stays green) | `test_structured_agent_prompts.py` + `test_structured_agents.py` | ALWAYS_PASSES | PASS (48 passed) |
| R-06 | Env-override machinery regression (unknown vars ignored, coercion, invalid values raise) | `test_env_overrides.py` | ALWAYS_PASSES | PASS (23 passed) |
| R-07 | CLI surface regression set (display / prefs / precedence / env-skip / commands) | `test_cli_display.py` + `test_cli_prefs.py` + `test_cli_config_precedence.py` + `test_cli_env_skip.py` + `test_cli_commands.py` | ALWAYS_PASSES | PASS (67 passed) |
| R-08 | Flake watch: `TestLoadOhlcvNoPoison` (the file e02s02 touched via quick-fix) stays green | `test_no_data_handling.py::TestLoadOhlcvNoPoison` | USUALLY_PASSES | PASS (1 passed, 0.24s) — no `--tb=long` capture needed |

## 3. Safety evals — can this hurt anyone?

| ID | Evals (one sentence) | Grader (code) | Tier | Result |
|---|---|---|---|---|
| S-01 | An unparseable / absent / refused decision returns **REVIEW**, never a fabricated or defaulted rating, and the memory log records REVIEW rather than a tradeable Hold | `test_signal_processing.py::{TestSignalProcessor::test_unparseable_signal_is_review_not_silent_hold, TestParseRating::test_no_rating_is_flagged_for_review_not_defaulted, TestGraphSignalContract::test_graph_surfaces_review}` + `test_rating_integrity.py::{test_prose_naming_several_ratings_without_a_label_needs_review, test_a_refusal_has_no_rating_and_is_not_defaulted, test_the_memory_log_records_review_rather_than_a_tradeable_hold}` | ALWAYS_PASSES | PASS (6 passed) |
| S-02 | The skip path never fabricates: the marker is non-empty and the skipped run still produces a 5-tier rating (never REVIEW); the policy skip does not claim a judge alignment finding | `test_debate_gate.py::{test_marker_is_never_empty_so_a_missing_transcript_cannot_read_as_empty, test_skip_path_process_signal_is_a_five_tier_rating, test_research_manager_skip_path_still_yields_a_five_tier_rating, test_never_policy_marker_does_not_claim_a_judge_alignment_finding}` | ALWAYS_PASSES | PASS (4 passed) |
| S-03 | Vendor failures are never silently swallowed: primary errors surface in logs, optional categories degrade with a warning, core categories still raise the taxonomy | `test_vendor_routing.py::VendorRoutingTests::{test_primary_error_is_logged_not_masked, test_optional_category_degrades_instead_of_raising, test_core_category_still_raises_on_error}` + `test_vendor_errors.py` | ALWAYS_PASSES | PASS (10 passed) |
| S-04 | A gate failure is never silent: WARNING logged with the instrument, debate held, E2E fallback observed | `test_debate_gate.py::{test_gate_exception_is_fail_safe_and_logged, test_gate_logging_warning_still_names_the_ticker_on_failure, test_gate_failure_end_to_end_falls_back_to_the_debate}` | ALWAYS_PASSES | PASS (3 passed) |
| S-05 | No secrets in logs: every planted provider-credential value is absent from all gate log records and from both rendered CLI surfaces; the judge request payload (all four analyst reports) never reaches a log record; the env notice names the variable and never its value; the delta's log-adjacent modules reference no credential identifier | `.venv/bin/python /tmp/phase5-evals-e02/s05-no-secrets.py` — plants a sentinel for **every** `PROVIDER_API_KEY_ENV` value, captures all root-logger records at DEBUG across the four gate paths (always / never / auto-skip / auto-fail) plus `write_report_tree` + `display_complete_report` + `resolve_debate_gate`, then asserts absence | ALWAYS_PASSES | PASS (63 log records scanned, 0 credential leaks, 0 payload leaks) — after 1 grader repair |

## 4. Results summary (pass@k)

k = 1 for every eval: all graders are deterministic code graders (pytest node ids and
shell gates), so a repeat run estimates nothing new. No model grader and no rubric grader
in this set. Per the run-evals promotion rule, all graders enter this report at
`ALWAYS_PASSES` **except** R-08 (`USUALLY_PASSES`, the historical flake watch). The tier
is justified by the story-level evidence already in the repo — the three verify records
(`specs/verifications/e02s0{1,2,3}-verify-*.yaml`) and the three audits
(`AUDIT-e02-e02s0*.md`) report the same suites green at each round, plus green Preflight
at each landing — and by this run's own first-attempt green result for every grader
(N=1 here, which is all a deterministic code grader can contribute).

| Class | Evals | Passing | Failing | Flaky |
|---|---|---|---|---|
| Capability | 20 (C-01 … C-20) | 20 | 0 | 0 |
| Regression | 8 (R-01 … R-08) | 8 | 0 | 0 |
| Safety | 5 (S-01 … S-05) | 5 | 0 | 0 |
| **Total** | **33** | **33** | **0** | **0** |

**pass@1: 33/33 grading units; 0 flaky.**

Raw evidence:

- Every grader's command, tail output and `RESULT` line: `/tmp/phase5-evals-e02/results.txt`
- Machinery: `/tmp/phase5-evals-e02/run-all.sh` (serial runner), the four shell graders
  `g16-…` … `g19-…`, and `/tmp/phase5-evals-e02/s05-no-secrets.py`
- 327 pytest node executions across 17 test files; `ruff check .` clean.
- Directly exercised against the **delivered** tree at `dc9c5c1` (= `b883f43` + specs
  bookkeeping only).

### Delegated legs (not run here, by instruction)

| Leg | Grader command | Why not run here |
|---|---|---|
| R-00 — whole-suite Preflight | `cd /home/maplewong1998/Repository/TradingAgents && .venv/bin/python -m pytest -q && .venv/bin/python -m ruff check .` | The Phase-5 brief says **do not run the full suite**: a sibling fleet child owns the full-suite legs in a separate worktree. This run covers the lint leg (R-01) and 8 targeted root-level suite legs (R-02 … R-08) instead. `ps -eo pid,args | grep -E "[p]ytest"` was empty before every grader, so no overlap was observed. |

## 5. Eval gaps (test-plan scenarios with no runnable grader)

**None at scenario level.** All 18 scenarios in `e02-TEST_PLAN_LATEST.md` map to at least
one grader that ran green here:

| Scenario | Grader(s) |
|---|---|
| SC-e02s01-P0-01 | C-03, S-04 |
| SC-e02s01-P0-02 | C-04 |
| SC-e02s01-P0-03 | C-02 |
| SC-e02s01-P0-04 | C-01, C-05, S-02 |
| SC-e02s01-P0-05 | C-05, S-02 |
| SC-e02s01-P1-01 | C-06 |
| SC-e02s01-P1-02 | C-07 |
| SC-e02s01-P1-03 | C-05, R-05 |
| SC-e02s01-P1-04 | C-08 |
| SC-e02s01-P1-05 | C-04 |
| SC-e02s01-P2-01 | C-09 |
| SC-e02s02-P1-01 | C-10, R-04 |
| SC-e02s02-P1-02 | C-11 |
| SC-e02s02-P2-01 | C-12, C-14, C-20 |
| SC-e02s02-P2-02 | C-13, C-14 |
| SC-e02s02-P2-03 | C-11 |
| SC-e02s02-P3-01 | C-15, S-04 |
| SC-e02s03-P2-01 | C-16, C-17 |
| SC-e02s03-P3-01 | C-18 |

Residual coverage notes (recorded, not gaps — each has a runnable green grader):

- **SC-e02s02-P2-01, "wall-time tracker unaffected".** Now graded by C-20
  (`test_analyst_execution.py`, whose `test_syncs_wall_time_from_sequential_chunks`
  exercises the chunk-sync path that `cli/stream_handler.py` reuses). The assertion is
  indirect: no test drives the wall-time tracker *through* `apply_value_chunk` with a gate
  skip in the chunk stream. See § 6 for the first-class-suite suggestion.
- **SC-e02s02-P2-02, "in all three modes" for the CLI **display**.** C-13's
  `test_the_complete_report_display_carries_the_gate_section` asserts the skipped mode on
  screen; the held- and never-modes are asserted on the saved report tree
  (`test_report_tree_counts_a_held_debate_in_turns`,
  `test_report_tree_names_a_configuration_skip`) and both modes share one renderer
  (`render_debate_gate_section`). SC-e02s02-P2-02's Level is "Unit (tmp_path)".
- **SC-e02s03-P2-01 / P3-01** are grep-gates by design (the test plan marks them
  "grep-gate (runnable)"); C-16/C-17/C-18 are exactly that.

## 6. Grader repairs and flake handling

- **C-19 first run FAILed** with `sed: -e expression #1, char 42: unknown option to 's'`.
  Cause: the grader's own `sed` delimiter `/` collided with the path
  `tradingagents/graph/trading_graph.py`. Fixed by rewriting the row lookup as
  `awk -F'|'` with the *same* assertions. Re-run 1: PASS.
- **S-05 first run FAILed** with `TypeError: str expected, not NoneType` at
  `os.environ[_env_var]`. Cause: `PROVIDER_API_KEY_ENV` maps `bedrock` and `ollama` to
  `None`. Fixed by skipping `None` values; no assertion weakened. Re-run 1: PASS.
- Both were **defects in the eval definitions written here**, not product failures and not
  flake; they are reported as PASS at run 1 after repair, not as FLAKY.
- **FLAKE WATCH** (`tests/test_no_data_handling.py::TestLoadOhlcvNoPoison`, the file the
  e02s02 quick-fix touched): PASS on its first and only run (1 passed in 0.24s). No
  `--tb=long` capture was required, so `/tmp/e02_phase5_flake_no_data_handling.txt` was
  never written.
- No other grader needed a second run. `ps -eo pid,args | grep -E "[p]ytest"` was checked
  before the serial run and returned empty (only the IDE's own `ruff server` processes were
  alive); no unknown third-party process was observed competing for the tree.

## 7. Evals worth adding as first-class suite members (post-release)

Ranked by the risk they would close; each is a candidate `tests/` member for the next
cycle, not a change made in this read-only phase.

1. **`_run_signature` round-trip matrix (C-10 extension).** Today three nodes cover
   gate-mode changes. A parametrised case per config dimension (analysts, debate depth,
   risk depth, asset type, portfolio fingerprint, gate mode) would pin the "graph shape is
   encoded in three places" hazard (`tech-stack.md` § gray areas) once instead of per story.
2. **Wall-time + status integration through the real chunk stream (C-20 extension).**
   Drive `apply_value_chunk(..., wall_time_tracker=…)` with a gate-skip chunk sequence and
   assert both the `skipped` statuses and a coherent wall-time summary — closes the
   indirect-coverage note above.
3. **Mode × surface matrix for the Debate Gate section.** One parametrised test over
   (auto-skip, held, never) × (saved tree, on-screen display) instead of split assertions;
   guards the "all three modes" wording of SC-e02s02-P2-02 literally.
4. **`debate_gate` precedence truth table in one place.** Env × prefs × saved config ×
   default, asserting the winner *and* the notice text (currently spread across
   `test_cli_config_precedence.py` and `test_cli_env_skip.py`); mirrors the existing
   round-count table so a future precedence change has one place to fail.
5. **Doc-gate promotion (C-16/C-17/C-18).** These three shell greps have now passed at
   three story-level verify rounds and this Phase-5 round. Promoting them into a
   `tests/test_docs_contract.py` (or a `scripts/` doc gate wired into Preflight) would stop
   a later doc refactor from silently dropping the `always` restore statement — the same
   class of drift the repo already guards for specs layout via
   `scripts/validate-specs-yaml.sh`.
6. **`no secrets in logs` as a re-usable helper (S-05).** The sentinel-planting capture is
   generic; a shared `tests/conftest.py` fixture (`captured_logs_with_sentinel_keys`) would
   let any future logging surface adopt the same guard in one line.

## 8. Read-only attestation

- `git status --short` (tracked) at the end of the run: **empty**. `git status --short`
  full output: empty. HEAD unchanged at `dc9c5c1` before and after grading.
- Every artefact of this phase lives outside the repo:
  `/tmp/phase5-evals-e02.md` (this file) and `/tmp/phase5-evals-e02/` (runner, 4 shell
  graders, the S-05 script, `results.txt`).
- pytest ran with `-p no:cacheprovider` and `PYTHONDONTWRITEBYTECODE=1`; `ruff check .`
  is read-only.
