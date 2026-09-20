# AUDIT — e02/e02s01 (gate round 1)

<!-- story: e02s01 -->

- **Skill:** `audit-code --gate` (non-interactive CI-gating mode) + `request-review` 94% AND gate
- **Auditor:** resident `gate` gatekeeper (819cb80f-4f31-40ec-97bf-72bfbac92137), round 1
- **Branch:** `feat/e02-conditional-debate-gate` @ `6a9f155` (repo root; no separate worktree)
- **Diff audited:** `git diff 534782e..HEAD` (frozen-plan baseline → story commits 114f769, 2fb2bcb,
  f429cfa, 95f5c40, 23f69fa, 45c7799, 6a9f155) + untracked record artifacts
  (`specs/verifications/e02s01-verify.yaml`, `specs/fleet-agents.yaml`)
- **Date:** 2026-09-20 (auditor-local +0800)
- **Verdict: PASS — score 98 (40/41), hard sections all PASS, 0 HIGH security findings**
- Working tree carried unstaged orchestrator edits (`progress.md`, `specs/state.yaml`); the audit
  judged the committed delta only. The auditor wrote nothing except this report (read-only otherwise);
  all scratch output went to /tmp.

## Churn-ranked review order

`scripts/bp-churn-rank.sh --since 90.days`: `trading_graph.py` (16 commits — highest churn AND
touched here, reviewed first), `agents/schemas.py` (6), `default_config.py` (5), then remaining
changed files. `tests/test_debate_gate.py` and `agents/gate/*` are new (churn 0) and got the full
checklist regardless — churn sets priority, not scope.

## Adjudicated context applied (not re-litigated)

1. `DebateGateVerdict`/`render_debate_gate_marker` live in `tradingagents/agents/gate/schemas.py`,
   re-exported from `agents/schemas.py` (at the §File-Size Exceptions cap). The +13-line re-export
   growth of `agents/schemas.py` (379→392) is therefore **exempt** from the file-size FAIL below.
2. Skip predicate implements frozen SC-e02s01-P0-04 (skip iff `evidence_aligned` AND
   `confidence != "low"` AND `aligned_direction in {bullish, bearish}`) — verified in code
   (`debate_gate.py:143-156`) and pinned by tests (`tests/test_debate_gate.py:320-336`, :270-294).
3. Held-debate Research Manager paragraph byte-identical — **independently confirmed** by AST
   extraction: the string constant at `research_manager.py:47` is byte-equal to the pre-story
   prompt line at 534782e:39; the `#1321` pin (`tests/test_structured_agents.py:500-506`,
   `inspect.getsource(create_research_manager)`) passes.

## Independent re-runs (serial, no concurrent pytest; pgrep pre-check clean)

| Command | Result |
|---|---|
| `.venv/bin/python -m pytest -q` (run 1) | **1 FAILED** (`test_no_data_handling.py::TestLoadOhlcvNoPoison::test_empty_download_raises_and_does_not_cache`), 999 passed, 2 skipped — see Discovered Defects |
| same test isolated | passed (0.34s) |
| `.venv/bin/python -m pytest -q` (runs 2-5) | 1000 passed, 2 skipped ×4 |
| `.venv/bin/python -m pytest -q` (runs 6-15, full output captured) | 1000 passed, 2 skipped ×10, 0 failures |
| `ruff check .` | All checks passed! |
| `.venv/bin/python -m pytest -q tests/test_debate_gate.py` | 54 passed in 0.48s |

Preflight is green and deterministic on the current tree (14 consecutive full-suite greens after
the single transient failure). Verify-round evidence ("1000 passed, 2 skipped, ruff clean") is
independently reproduced.

## Checklist (audit-code full, --gate)

### Supply Chain & Security — PASS (5/5)

- ✓ slopcheck: no new dependencies (pyproject untouched in diff); spec §Slopcheck tags
  `langgraph` **[OK]**, `pydantic` **[OK]**; Discovery Mandate verified `langgraph.types.Command`
  against installed langgraph 1.2.11.
- ✓ No `[SLOP]` packages.
- ✓ No secrets in diff — scanned full `534782e..HEAD` for `sk-`, `ghp_`, `AKIA`, PEM headers,
  `api_key=` literals: clean (only false positive: prose "ri**sk-**debate").
- ✓ OWASP spot-check: no `eval/exec/subprocess/pickle/os.system/unsafe-yaml` added; no auth
  surface; no new sensitive-data exposure (judge prompt contains analyst reports only — data
  already flowing to LLMs pre-story; prompts are never logged, only `verdict.rationale`);
  misconfiguration hardened (env validation `default_config.py:65-82` + graph-init validation
  `trading_graph.py:94-107,132-137` + in-node unknown-mode fail-safe `debate_gate.py:90-95`).
- ✓ Security scan performed (mandatory — diff touches external LLM APIs): **0 HIGH, 0 MED, 2 LOW**
  (below). No `specs/security/EXCEPTIONS.md` needed (no deviations, no open HIGH).

**Security findings**

| Sev | Finding | Bounding |
|---|---|---|
| LOW | Prompt-injection surface: analyst reports embed external news/social content that is interpolated into the judge prompt (`debate_gate.py:107-126`); adversarial content could attempt to steer an `evidence_aligned` skip. | Skip only possible from a pydantic-validated `DebateGateVerdict` with `confidence != low` AND definite direction; worst case is reduced deliberation depth — RM, Trader, risk debate and PM all still run; decision + rationale persisted in `debate_gate_verdict` for audit; any judge anomaly fails safe INTO the debate. No new trust boundary (the same content already reaches every downstream agent). |
| LOW | never-mode synthetic marker (`debate_gate.py:73-88` → `_skip`) renders "The four analyst reports are aligned (unclear) at medium confidence" though no judge ran; e02s02 report surfaces could misread it as a judge finding. | The `rationale` text explicitly says the judge is disabled; wording fix routed (verify finding #2). |

Also verified: every fallback path logs a WARNING (#989 house rule — `_fail_safe`
`debate_gate.py:185-197`; `bind_structured` logs its own warning); no free-text retry on judge
failure (pinned by `test_a_failed_gate_does_not_retry_as_free_text`); rating integrity preserved —
unparseable → REVIEW rule untouched, skip path yields a 5-tier rating (SC-e02s01-P0-05 tests, unit
+ E2E).

### Provenance & Metadata — PASS (2/2)

- ✓ Story spec carries `**type:** feat` and `**context:** domain` (e02s01-gate-core-routing.md:5-7).
- ✓ Decisions cite commit SHAs (state.yaml/progress.md: 114f769, 2fb2bcb, 23f69fa, 45c7799) and
  code comments cite motivating issues (#1176, #1088, #1170, #1321, #989, #1130, #994 class).

### Law of Demeter — PASS (2/2)

- ✓ No message chains (`a.getB().getC()`); gate reads state keys directly and calls immediate
  collaborators only (own `schemas`, `agent_utils`, `structured`, `dataflows.config`).
- ✓ No law violations needing justification.

### CONVENTIONS.md Compliance — PASS (4/4)

- ✓ Story planning/verification output all in `specs/` (epic capsule, verify yaml, this report).
  `progress.md` sits at project root — it is the **orchestrator's** fleet-notes record artifact
  (written in `chore(specs)` commits, sanctioned by the fleet setup), not a story document;
  routed as a record-layer note under ruling A10 (relocate under `specs/` or document the exception).
- ✓ No `gh issue create` anywhere in the diff.
- ✓ No `gh` usage at all in the diff.
- ✓ No direct GitHub REST calls (no curl/fetch to api.github.com).
- Traceability mandate: `# story: e02s01` tag present (tests/test_debate_gate.py:1); scenario IDs
  `SC-e02s01-*` referenced per convention; conventional-commit shapes correct
  (`test(agents)`, `feat(agents)`, `fix(agents)`, `chore(specs)`), no AI-attribution trailers.

### Scope — PASS (5/5)

- ✓ All 16 changed files map to ledger tasks 1-9: gate package (task 3), schemas re-export
  (task 2, adjudicated), AgentState field (task 4), propagation init (task 4), setup.py wiring
  (task 5), RM prompt (task 6), default_config + trading_graph validation (task 7), test suite
  (tasks 1/8), specs metadata (workflow bookkeeping). `conditional_logic.py` untouched — spec
  contract "should_continue_debate semantics untouched" honored; its `"Bull Researcher"` return
  (:61) is the intra-debate loop router, not a gate bypass (only analyst-phase entry edge now
  routes through `Debate Gate`).
- ✓ No speculative features: never-mode synthetic verdict, `_GATE_FAILURE_VERDICT` audit string and
  the sync-test for the duplicated mode list all trace to spec text/scenarios; no premature CLI or
  checkpoint wiring (grep `debate_gate` in `cli/` → empty; `_run_signature` deferral is spec'd to e02s02).
- ✓ No files touched outside the stated scope. (Zoom-Out table omits `trading_graph.py` /
  `agent_states.py` though tasks 4/7 mandate both — spec-record gap, routed note.)
- ✓ **Discovered defects (fix-or-log):** one transient red Preflight observed and investigated —
  see Discovered Defects section. Not reproducible (1 failure across 15 full runs; 14 consecutive
  greens since); story diff causally excluded; routed for log + hardening. Always Green holds on
  the current tree.
- ✓ Boy Scout applies to files opened for gate failures — none opened for fixes (auditor is read-only).

### Boy Scout Rule — PASS (3/3)

- ✓ Touched files cleaner: WHY-comments with issue citations throughout (house's strongest
  convention, exemplified — e.g. `debate_gate.py:41-52`, `setup.py:88-90`, `default_config.py:74-81`).
- ✓ No dead code (test `_GateLLM.invoke` free-text counter is exercised by the no-retry test).
- ✓ No commented-out code blocks.

### Types and Safety — PASS (3/3)

- ✓ No `any`/untyped **public** functions beyond house shape: `create_debate_gate` is the only
  factory in the repo with an annotated return type (`Command[Literal[...]]`, statically asserted
  by `test_gate_declares_its_targets_as_a_literal_union`); its bare `quick_llm` param matches all
  13 sibling `create_*(llm)` factories (CONVENTIONS: "match that shape"). Routed LOW:
  `_fail_safe(state, exc: Exception)` receives a `str` at `debate_gate.py:97` — widen to
  `Exception | str` or wrap.
- ✓ No new type/lint suppressions bypassing safety: the single `# noqa: E402,F401`
  (`agents/schemas.py:389`) is the mechanical consequence of adjudicated ruling 1 and matches the
  house re-export precedent verbatim (`social_media_analyst.py:13 # noqa: F401`), with a WHY comment.
- ✓ No casts, no `type: ignore` added (diff grep clean).

### Test Coverage — PASS (4/4)

- ✓ Every new function tested: gate node + factory (routing matrix, 6 hold cases + 4 skip cases,
  failure/None/unknown-mode/missing-key), schema + marker (validation, rejection, direction
  propagation), `_validate_override` (env accept ×3 / reject), `_coerce_debate_gate` (graph-init
  ValueError naming all modes), propagation field, AgentState annotation, RM prompt variants
  (skip/held/rating-integrity), mode-list sync guard, graph wiring (node registration, Command
  targets ⊆ compiled nodes), E2E (`always` sequence + zero judge calls; skip never invokes
  Bull/Bear; `process_signal` 5-tier ≠ REVIEW; gate failure end-to-end holds debate).
- ✓ Regression test for the bug fix: predicate correction shipped test-first — `23f69fa`
  (test-only, +38/-1, failed in isolation per progress.md) → `45c7799` (product-only predicate
  flip). Commit shapes verified via `git show --stat`.
- ✓ Tests exercise public interfaces (factory-built node invoked with a state dict; real
  `GraphSetup` graph compiled and streamed with boundary-stubbed agents; judge LLM faked at the
  `with_structured_output` boundary — never the thing under test).
- ✓ **F.I.R.S.T (`enforce-first --quick` on tests/test_debate_gate.py — the only new/modified
  test file): 3/3 criteria pass, 0 violations.**
  - *Fast:* 54 tests in 0.48s; fully offline (fake LLMs, mocked analysts, no network).
  - *Independent:* `_policy` swaps/restores `config_module._config` in `finally`; env tests use
    `monkeypatch` + `importlib.reload` (house pattern with precedent in `test_env_overrides.py:12-18`;
    the file's last config test leaves a clean no-env reload); passes in isolation and in-suite.
  - *Self-Validating:* concrete asserts only (exact `goto` targets, marker string equality,
    invocation counts == 0/1, WARNING levelno, 5-tier membership + `!= REVIEW`); no manual inspection.
  - Note (not a violation): `test_node_sequence_with_always_matches_the_unconditional_debate`
    (:826) asserts required-node presence + Bull<Bear<RM ordering + zero judge calls rather than
    strict sequence equality vs a pinned pre-story baseline — weaker than the scenario's "equals"
    wording. Routed (verify finding #1/#3).

### SOLID and Heuristics — PASS (4/4)

- ✓ SRP: `debate_gate.py` = routing policy only; verdict schema/render in `gate/schemas.py`;
  config validation in `default_config.py`; nothing unrelated bundled.
- ✓ OCP: extended via a new node + policy modes; `conditional_logic.py` and the debate loop
  (stable code) untouched; factory shape reusable for the deferred risk-debate gate.
- ✓ DIP: judge LLM injected (`create_debate_gate(quick_llm)`); policy read through the house
  config seam (`get_config()` at invocation, cf. `get_language_instruction`), not a global import.
- ✓ Chapter 17: G5 — the one duplication (`_DEBATE_GATE_MODES` copy) is documented with its
  constraint (circular import at config-build time), WHY-commented, and guarded by
  `test_the_two_valid_mode_lists_stay_in_sync`; G25 — modes are a named constant, no magic
  strings scattered; G28/29 — see Code Style #7; T5 — boundary conditions exhaustively tested
  (None verdict, exception, unknown mode, absent policy key, low confidence, mixed/unclear/no
  direction, empty report → "not available" marker, non-English reports); F1 — ≤2 params
  everywhere in production code (test helper `_noop` takes 5 — scaffolding, noted); F4 — no dead
  functions; C-comments — no redundant/metadata comments, no commented-out code.

### Refactoring Smells (Fowler) — PASS (1/1) — smells explicitly named

- **Middle Man:** `agents/schemas.py` re-export block — adjudicated (ruling 1), keeps the public
  import path stable; not counted against.
- **Duplicated Code:** mode-list copy — justified (circular import), commented, sync-tested.
- **Primitive Obsession:** `debate_gate` mode as a plain string — matches the house config pattern
  (all config values are primitives); typed at the boundary by `_coerce_debate_gate` + Literal set.
- **Mysterious Name / Feature Envy / Message Chains / Data Clumps:** none detected.

### Code Style (CONVENTIONS.md) — FAIL (1 item) → 7/8

- ✓ Functions 4-20 lines — **calibrated PASS** (declared, not silent): the section is scoped to
  CONVENTIONS.md, which makes ruff the style authority (ruff is clean) and mandates the `create_*`
  closure shape; every existing node closure is 54-85 lines (`research_manager_node` 80,
  `portfolio_manager_node` 77, `trader_node` 75, `bull_node` 54). `debate_gate_node` (98 lines,
  `debate_gate.py:59-156`) matches that house shape and is ~55% prompt text. Advisory routed:
  extract `_judge_prompt(state)` (would land the node at ~40 logic lines).
- ✓ Stepdown — same calibration: the node is early-return policy branches → one judge call → one
  routing decision; the inline prompt is data, not a second abstraction level of logic. Advisory
  routed with the extraction above.
- ✗ **Files under 300 lines / §File-Size Exceptions "MUST NOT grow further":**
  `tradingagents/graph/trading_graph.py` grew **672 → 696** (`_coerce_debate_gate` :94-107,
  init-validation block :132-137, import :15) while listed in CONVENTIONS §File-Size Exceptions
  (672) under an explicit no-growth rule that also appears in AGENTS.md's Never list
  ("Never let a file in § File-Size Exceptions grow further — extract first"). **Not covered by
  any adjudicated ruling** (ruling 1 exempts only `agents/schemas.py`). Extraction was feasible:
  the helper could live beside `DEBATE_GATE_MODES` in the gate package (already imported here) or
  in a small `graph/` validation module. Risk tier P2 [file-size-cap] → fix same epic or next
  (e02s02); non-blocking for this gate. `tests/test_debate_gate.py` (885) follows house test-file
  practice (`test_memory_log.py` 1042; the exceptions table tracks library files only).
- ✓ Names specific/unique: every new name greps to a single entity; `_skip`/`_fail_safe`/
  `_empty_debate_state`/`weighing_paragraph`/`render_debate_gate_marker` have no foreign collisions.
- ✓ No duplication (DRY) beyond the justified, guarded mode list.
- ✓ Early returns over nested ifs; max 2 indentation levels in new code.
- ✓ Conditionals as positives (G29): the hold predicate (`debate_gate.py:143-148`) is a
  disjunction of doubts over positively-named fields — not the G29 anti-pattern (negated
  negative-name); it reads as the frozen conservative contract and is commented per clause.
- ✓ Comments explain WHY, cite issues, and docstrings state contract + failure mode (house rule).

### Red Flags — rationalizations explicitly named (none silent)

1. *Function-length/stepdown items calibrated to CONVENTIONS.md instead of the generic 4-20
   default* — declared above with house-precedent measurements; the generic rule would fail every
   existing node closure in this repo, and the section header scopes these items to CONVENTIONS.md.
2. *`progress.md` at project root not failed under CONVENTIONS Compliance* — it is the
   orchestrator's own fleet-notes record (chore commits, fleet-sanctioned; the gatekeeper role
   itself is chartered to write "progress notes"), so under ruling A10 it is a record-layer defect,
   routed, not scored.
3. *Transient Preflight red not failed under Scope #4* — the item's trigger is a **reproducible**
   gate failure; this one did not reproduce (1/15 full runs, 14 consecutive greens since, passes
   isolated), the story diff provably does not touch the test or its causal module, and the
   fix-or-log duty is routed with evidence rather than dismissed (no banned phrase applied —
   it was investigated, isolated, and a mechanism class identified).
4. *`# noqa` not failed under Types & Safety* — it implements adjudicated ruling 1 and matches
   verbatim house precedent; failing it would re-litigate the ruling.

## Score computation

Total checklist items: 5+2+2+4+5+3+3+4+4+1+8 = **41**. Passed: **40** (Code Style item 3 FAIL;
F.I.R.S.T counted inside Test Coverage item 4 — 0 violations, item PASS).
`score = round(100 × 40 / 41) = round(97.56) = **98**`.

## Gate decision (AND gate)

| Condition | Result |
|---|---|
| Supply Chain & Security FAILs | 0 → PASS |
| Types and Safety FAILs | 0 → PASS |
| Test Coverage FAILs (incl. F.I.R.S.T) | 0 → PASS |
| Scope FAILs | 0 → PASS |
| Open HIGH security findings / EXCEPTIONS.md | 0 HIGH; none needed → PASS |
| Score ≥ 94 | 98 → PASS |

**VERDICT: pass** (hard sections: code PASS / test PASS / security PASS).

## Discovered Defects — investigation log (transient Preflight red)

- **Observed:** full-suite run #1 at 6a9f155 (this audit, ~12:51 local):
  `FAILED tests/test_no_data_handling.py::TestLoadOhlcvNoPoison::test_empty_download_raises_and_does_not_cache`
  (1 failed, 999 passed, 2 skipped). Traceback not captured (only tail retained); pytest
  `lastfailed` cache since cleared by green runs (`{}`).
- **Reproduction attempts:** isolated run → passed; 14 further full-suite runs (4 + 10 with full
  capture) → all `1000 passed, 2 skipped`. **Not reproducible.** No ordering randomizer installed
  (pytest 9.1.1, fixed alphabetical order, no pytest-randomly), so order-swap flakiness is excluded.
- **Story causality excluded:** `tests/test_no_data_handling.py` and
  `tradingagents/dataflows/stockstats_utils.py` are untouched by `534782e..HEAD` (last changed at
  e3bc872/29e331a, pre-baseline). The test asserts `load_ohlcv("FAKE", ...)` raises
  `NoMarketDataError` on a mocked-empty download and writes nothing to `tests/_tmp_cache`.
- **Mechanism class:** the test is non-hermetic — fixed shared path `tests/_tmp_cache` (not a
  pytest `tmp_path`, not gitignored), no stale-state cleanup in `setUp`. A leftover non-empty
  `FAKE-YFin-data.csv` (residual state predating this session — `load_ohlcv` serves a fresh
  non-empty cache before raising, `stockstats_utils.py:226-243`) or a concurrent-process race on
  the directory (the fleet's own progress notes warn about concurrent-pytest races in this repo)
  fails it exactly once; the failed run's `tearDown` consumes the state (self-healing), matching
  the observed 1-then-14-greens pattern. `tearDown` also `os.rmdir`s a directory that an
  interrupted run leaves behind.
- **Disposition (fix-or-log ladder, reproduction genuinely blocked → LOG):** routed — write a
  `specs/bugs/BUG-*.md` entry + registry line (auditor cannot: read-only by role), and quick-fix
  the hermeticity (use `tmp_path` or purge stale `tests/_tmp_cache` at `setUp`). Ship as a
  separate commit on this branch per CONVENTIONS "discovered fixes ship in the same PR".
  Related pre-existing sibling: BUG-2026-09-20-ohlcv-cache-freshness-tz (fixed) documents the same
  module's time-sensitive test family; the workstation runs at +0800 while CI is TZ=UTC.

## Routed infrastructure notes (pre-existing, not story-caused)

- `scripts/check-import-boundaries.sh` fails for everyone: `specs/import-boundaries.json` has
  never existed in git history; script is not wired into Preflight or `ci.yml`. Direct grep
  confirms the substance holds: no `cli/` imports inside `tradingagents/`.
- `scripts/trace-stories.sh --strict` reports "story count 5 below baseline 50" (global-install
  baseline mismatched to this young repo); not wired into `ci.yml` even though CONVENTIONS.md:79
  says CI enforces it. Substance holds: e02s01 has its `story:` tag + scenario IDs.
- `ci.yml` = pytest matrix + clean-install smoke + ruff only.
- CONVENTIONS.md §Tests does not enumerate the F.I.R.S.T rubric words, so `enforce-first`'s
  mechanical self-check grep fails (grep2=1) — wire the rubric into §Tests (seed-conventions pass).

## Record integrity (non-blocking — ruling A10; never scored, never gate-blocking)

Each with reproduction:

1. `specs/epics/e02-conditional-debate-gate/e02s01-gate-core-routing.md:9` still reads
   `status: failing` while the ledger is `passing` (repro: `grep -n "status:" <spec> | head -1`;
   flips when the story lands — already noted by verify).
2. Spec §17 SC-e02s01-P0-04 (spec:116-119) omits the `aligned_direction` clause that the frozen
   routing matrix and the implemented predicate include (repro: read spec:116-119 vs
   `debate_gate.py:143-148`; frozen text — e02s03 docs pass should annotate).
3. Spec Zoom-Out table (spec:23-30) omits `graph/trading_graph.py` and `agents/utils/agent_states.py`
   although tasks 4/7 mandate touching both (repro: compare table rows with
   `git diff --name-only 534782e..HEAD`).
4. `specs/state.yaml` handoff note enumerates accepted divergences "(a) … (c) …" with no "(b)"
   (repro: read the note; divergence 2 was the rejected predicate, since corrected).
5. `progress.md` (project root) is orchestrator narrative stored outside `specs/` — relocate or
   document (see CONVENTIONS Compliance item 1).
6. `progress.md:32-33` cites TDD commits `737a3b4`/`c76a862` that do not exist in git history;
   the note itself flags the mismatch and defers to git log (114f769/2fb2bcb) — self-corrected record.

## Fix guidance (fix-forward; none gate-blocking)

Priority order for the next touches of this code (e02s02 develop or a quick-fix commit):

1. **[P2 file-size-cap — the single scored FAIL]** Extract `_coerce_debate_gate`
   (`trading_graph.py:94-107`) out of the exceptions-capped facade — natural homes: beside
   `DEBATE_GATE_MODES` in `tradingagents/agents/gate/` (already imported) or a small
   `tradingagents/graph/config_validation.py` (could take `_coerce_max_tokens` with it). Keep the
   `TradingAgentsGraph.__init__` validation call (task-7 contract). Then `trading_graph.py` must be
   back at ≤672 lines, or the §File-Size Exceptions row updated with orchestrator sign-off.
2. **[discovered defect]** BUG-log + hermeticity fix for
   `tests/test_no_data_handling.py::TestLoadOhlcvNoPoison` (tmp_path / setUp purge of stale
   `tests/_tmp_cache`); separate commit on this branch.
3. **[LOW]** `debate_gate.py:97`: pass an exception instance (e.g.
   `RuntimeError("provider does not support structured output")`) or widen `_fail_safe`'s
   annotation to `Exception | str` — the current call contradicts the annotation.
4. **[LOW]** never-mode marker wording: distinguish the policy skip from a judge finding
   (`debate_gate.py:73-88` / `render_debate_gate_marker`) before e02s02 surfaces consume it.
5. **[test]** Strengthen `test_node_sequence_with_always_matches_the_unconditional_debate` (:826)
   to full sequence equality against a pinned pre-story expected list (or derive it by compiling
   the graph without the gate edge), per SC-e02s01-P0-02's "equals" wording.
6. **[cosmetic]** `debate_gate_node` reads `state["market_report"]` etc. directly — a bare
   programmatic caller omitting a key gets a KeyError instead of the "not available" marker;
   `state.get(..., "")` + `report_or_absent` would make the node total (all real graph paths
   pre-initialize, so cosmetic).
7. **[e02s02 must-do]** Mirror the graph-shape change into `_run_signature` (IMPACT_LATEST.md:48
   third place) so checkpoints cannot resume the wrong graph — deferred by plan; confirm it lands.
8. **[advisory]** Extract `_judge_prompt(state)` from `debate_gate_node` (stepdown/length).

## Handoff

Gate PASS at step 6 → orchestrator advances (step 6.5 F.I.R.S.T. enforcement: satisfied inline —
`enforce-first --quick` ran on the only new/modified test file, 0 violations → step 7).

---

# Round 2 — delta re-check (6a9f155 → d96645a)

- **Date:** 2026-09-20 (auditor-local +0800). Same resident gatekeeper; round-1 findings kept,
  only the delta re-derived. Read-only on the repo (scratch: /tmp/flake-repro, /tmp diffs);
  this report is the only write.
- **Delta commits:** c0e46ba refactor(agents) size-cap extraction · cc71f9f fix(tests) hermetic
  cache test + BUG log · 7a5d639 test(agents) RED policy-marker pin · 4d675a5 fix(agents) honest
  policy marker + annotation widen · cee9452 test(agents) strict pre-story sequence pin ·
  d96645a chore(specs). Delta stat: 11 files, +422/−98 (product: gate package, config_validation
  new, trading_graph; tests: debate_gate, no_data_handling; records: BUG spec, registry, progress,
  state).

## Item-by-item verification of the five routed fixes

1. **File-size cap (round-1's only scored FAIL) — CLEARED.** `trading_graph.py` 696 → **651**
   (frozen cap 672; 21 lines under the pre-story baseline). Per ORCHESTRATOR-RULED deviation
   (not re-litigated): `coerce_debate_gate_mode` moved beside `DEBATE_GATE_MODES` in
   `agents/gate/debate_gate.py` (rename-only — body byte-identical to the old `_coerce_debate_gate`
   save name/docstring, diff-verified); `_coerce_max_retries`/`_coerce_max_tokens` moved **verbatim**
   (AST-identical, machine-checked) to new `graph/config_validation.py` (46 lines, under cap, not
   in the exceptions table) and re-imported into the facade — re-import contract proven live:
   `from tradingagents.graph.trading_graph import _coerce_max_tokens, _coerce_max_retries` works.
   **`TradingAgentsGraph.__init__` validation PRESERVED** (my explicit requirement) and SC-e02s01-P1-02
   re-probed both ways: `TRADINGAGENTS_DEBATE_GATE=bogus` → `ValueError: Invalid value for
   TRADINGAGENTS_DEBATE_GATE: valid modes are always, auto, never` at config build; bogus config
   dict → `ValueError: Invalid debate_gate mode 'bogus'. Valid modes: always, auto, never.` at
   graph init. Develop's **zero-line setup.py claim verified**: `git diff 6a9f155..d96645a --
   tradingagents/graph/setup.py` = 0 lines. No other exceptions-capped file grew in the delta
   (`agents/schemas.py` stays 392 — unchanged since round 1, adjudicated; `cli/main.py`,
   `y_finance.py`, `openai_client.py`, `memory.py`, `stockstats_utils.py` untouched).
   `debate_gate.py` 236 < 300; `gate/schemas.py` 91 < 300.
2. **Flake fix-or-log — LANDED and independently re-derived.** `TestLoadOhlcvNoPoison` is now
   hermetic (`tempfile.mkdtemp(prefix="ta-no-data-handling-")` per test + `shutil.rmtree`,
   WHY-comment citing the BUG id). BUG spec
   `specs/bugs/BUG-2026-09-20-no-data-handling-nonhermetic-cache.md` + `registry.yaml` entry exist,
   P2/quick-fix, cite this audit. **Deterministic repro re-derived by the auditor in /tmp**
   (repo untouched): pre-fix test extracted via `git show cc71f9f^:` run against a planted fresh
   `_tmp_cache/FAKE-YFin-data.csv` (rows ≤ 2026-01-01, mtime today — fresh per
   `_cache_is_fresh(data_file, curr_date_dt, now)`, `stockstats_utils.py:181-192`) → **FAILED**
   exactly as diagnosed (cache served, `NoMarketDataError` not raised); HEAD hermetic test →
   **passed** (×4 subsequent runs). Round-1 mechanism confirmed; fix correct.
3. **`_fail_safe` annotation — FIXED**: `exc: Exception | str` (4d675a5), PEP 604 with
   `from __future__ import annotations` present. Round-1 LOW closed.
4. **Never-mode marker honesty — FIXED, test-first.** 7a5d639 is test-only (1 file, +45/−2) and
   structurally RED (asserts `"are aligned" not in marker` while the product at that commit still
   rendered the synthetic aligned verdict — cannot pass); 4d675a5 then adds
   `render_policy_skip_marker` (**pure addition** to `gate/schemas.py` — diff has zero deletion
   lines, so the judge-path `render_debate_gate_marker` is untouched) and routes never-mode through
   `_skip_by_policy(f"debate_gate={mode}")`. New marker: names the configuration, states "no Debate
   Gate judge was consulted", "no alignment finding", instructs the RM to decide from the four
   reports and commit to a 5-tier rating — no "are aligned" wording. Pinned by
   `test_never_policy_marker_does_not_claim_a_judge_alignment_finding` (wording both ways, marker ==
   `debate_gate_verdict`, zero judge calls) and `test_policy_skip_reaches_the_rm_with_a_marker_and_a_five_tier_rating`
   (real gate output → real RM → `process_signal` ∈ RATINGS_5_TIER, marker present in RM prompt).
   Round-1 security LOW #2 closed.
5. **Strict sequence pin — LANDED.** `test_node_sequence_with_always_matches_the_unconditional_debate`
   now asserts `[n for n in visited if n != GATE] == pre_story_sequence` (exact 10-node list) +
   `visited.count(GATE) == 1` + `llm.prompts == []` (zero judge calls). The pinned list matches the
   stub-harness topology deterministically and equals the sequence round-1's weaker test asserted by
   presence/ordering; provenance comment documents the `git archive 534782e` derivation. Round-1
   routed item closed.

## Pinned contracts re-verified at d96645a

- **Held-debate RM paragraph byte-identical to 534782e**: AST-extracted from both revisions —
  old 925-char f-string chunk vs new standalone 462-char constant; paragraph line **byte-equal**;
  `research_manager.py` has zero diff in the delta; `#1321` pin suite green.
- **Skip predicate (frozen SC-e02s01-P0-04)**: untouched by the delta (`debate_gate.py:143-156`
  logic unchanged apart from the never-mode branch replacement above it, which never reaches the
  predicate — policy short-circuit, spec'd "any verdict under never → Research Manager").

## Re-runs (serial; pgrep pre-check clean)

| Command | Result |
|---|---|
| `.venv/bin/python -m pytest -q` (Preflight leg, ×3) | **1002 passed, 2 skipped**, 88 subtests — matches develop's claim; 3/3 green |
| `ruff check .` | All checks passed! |
| `tests/test_debate_gate.py` | 56 passed in 0.48s (54 + 2 new) |
| `test_structured_agents.py + test_env_overrides.py + test_risk_router_path_map.py + test_ohlcv_cache_freshness.py` | 90 passed |
| `tests/test_no_data_handling.py` (file, ×3 + single ×1) | 3 passed each |

**Audit-session anomaly (disclosed):** the FIRST single-file run of the updated
`tests/test_no_data_handling.py` — its first import after the worktree moved to d96645a — reported
one-shot `1 failed, 2 passed` (0.55s vs 0.34s steady-state; traceback not captured, `tail -2`).
Not reproduced in the 7 consecutive runs since (1 single-test, 3 single-file, 3 full-suite). The
hermetic test is immune to shared-cache state by construction; other agents were demonstrably
active in this worktree between rounds (untracked `specs/TRACEABILITY_LATEST.md`,
`specs/traceability-matrix.json`, `specs/codebase-wiki/` appeared), so cross-process interference
during first-import/assertion-rewrite is the plausible class. Routed for awareness; no action
while non-reproducible.

## F.I.R.S.T (`enforce-first --quick` on the delta's new/modified tests)

`test_debate_gate.py` (+2 tests, sequence-test rewrite) and `test_no_data_handling.py` (hermetic
rewrite): **Fast** ✓ (all offline fakes/mocks; 56 tests 0.48s; 3 tests 0.34s) · **Independent** ✓
(mkdtemp per test — strictly more hermetic than before; `_policy` restore unchanged; passes
isolated and in-suite) · **Self-Validating** ✓ (strict list equality, exact wording assertions,
rating-set membership; no manual inspection). **0 violations.**

## Delta security review

Moves are AST-identical (no behavior change); `render_policy_skip_marker` interpolates only a
gate-validated mode string (`debate_gate={mode}`, mode ∈ Literal set) — no injection vector;
`_skip_by_policy` logs the configuration reason at INFO (explicit configured behavior, not a
silent fallback — #989 satisfied; the fail-safe WARNING path is unchanged). Round-1 LOW #2
(misleading never-mode marker) **closed**; LOW #1 (inherent bounded prompt-injection surface on the
judge) **stands by design**, bounded as documented in round 1. 0 HIGH, 0 MED, 1 LOW standing.

## Round-2 checklist re-derivation and score

Round-1 result carried for everything the delta does not touch (setup.py zero-diff, RM
byte-identical, `default_config.py`/`conditional_logic.py`/`propagation.py`/`agent_states.py`/
`agents/schemas.py` unchanged in delta). Delta judged against the full checklist: Supply Chain &
Security 5/5 · Provenance 2/2 (conventional commits ✓, BUG spec carries `story:` tag, decisions
cite SHAs) · Demeter 2/2 · CONVENTIONS Compliance 4/4 · Scope 5/5 (delta is exactly the five
routed items + record chore; no extras) · Boy Scout 3/3 · Types & Safety 3/3 (annotation fixed;
no new suppressions) · Test Coverage 4/4 (every new function tested — `coerce_debate_gate_mode`
via public surfaces, `_skip_by_policy`/`render_policy_skip_marker` directly; fix shipped test-first
with structurally-proven RED; F.I.R.S.T 0 violations) · SOLID/Heuristics 4/4 · Refactoring Smells
1/1 (named: cross-module private-name import is the adjudicated back-compat mechanism, documented
in `config_validation.py` docstring) · **Code Style 8/8 — round-1's file-size FAIL CLEARED**
(651 ≤ 672; new files 46/236/91 < 300).

**Score: 41/41 = 100.** Hard sections: Supply Chain & Security 0 FAIL · Types & Safety 0 FAIL ·
Test Coverage 0 FAIL · Scope 0 FAIL. 0 HIGH security findings.

**ROUND-2 VERDICT: PASS — score 100.**

## Routed notes after round 2

Closed this round: file-size cap FAIL; flake fix-or-log (BUG + hermetic fix, repro re-derived);
`_fail_safe` annotation; never-mode marker honesty; strict sequence equality.
Standing (non-blocking): (a) e02s02 MUST mirror the graph shape into `_run_signature`
(IMPACT_LATEST.md:48); (b) cosmetic `state[...]` KeyError exposure in `debate_gate_node`;
(c) advisory `_judge_prompt(state)` extraction (node 98 lines vs house 54-85); (d) cosmetic:
cross-module private-name imports (`_coerce_max_*`) — consider public aliases in a follow-up,
mechanism itself adjudicated; (e) BUG-registry follow-up: gitignore/ban `tests/_tmp_cache`,
consider suite-wide `tmp_path` config guard; (f) BUG spec snippet paraphrases
`_cache_is_fresh(data_file)` (actual signature 3-arg) — record-integrity nit, mechanism described
correctly (A10 non-blocking); (g) one-shot first-import anomaly above — awareness only;
(h) untracked non-story artifacts in the worktree (`specs/TRACEABILITY_LATEST.md`,
`specs/traceability-matrix.json`, `specs/codebase-wiki/`, `specs/fleet-agents.yaml`) — orchestrator
to commit or clean before release-branch.
Record integrity (A10, unchanged, non-blocking): spec header still `status: failing` (:9, flips at
landing); §17 P0-04 omits direction clause; Zoom-Out omits `trading_graph.py`/`agent_states.py`;
state.yaml divergence list skips "(b)"; `progress.md` at project root.
