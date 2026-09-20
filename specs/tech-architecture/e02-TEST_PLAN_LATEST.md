# Test Design: e02-conditional-debate-gate

<!-- plan-tests output — scenario IDs MUST be referenced by plan-work §17 Gherkin and by test files as `# scenario: SC-...` -->

Epic risk: **P1** (routing change + checkpoint signature + CLI display coupling).
Levels: everything below runs offline with fake LLMs — no live provider, no network
(CI has no keys; house rule). Suite baseline 2026-09-20: 946 passed / 2 skipped.

## 1. Risk Matrix & Scenarios

### P0 — critical (a miss silently changes trading decisions or crashes runs)

| Scenario ID | Behavior | Level | Story |
|---|---|---|---|
| SC-e02s01-P0-01 | Gate failure is fail-safe: structured call raises / returns None / unparseable → **debate runs**, warning logged, verdict recorded as gate-failure | Unit | e02s01 |
| SC-e02s01-P0-02 | `debate_gate=always` → node visit sequence **identical to current main** (Bull→Bear→…→RM), zero judge calls — regression guard for the default-behavior change | Integration (compiled graph) | e02s01 |
| SC-e02s01-P0-03 | Conflicted / ambiguous / low-confidence verdict → full debate runs exactly as today | Unit + Integration | e02s01 |
| SC-e02s01-P0-04 | Aligned + confident → debate skipped; RM receives an **explicit alignment marker**, never an empty transcript (#1176 fabrication class) | Unit | e02s01 |
| SC-e02s01-P0-05 | Rating integrity survives a skip: RM output on the skipped path still yields a parseable 5-tier rating (`process_signal` ≠ REVIEW) (#1170 class) | Unit | e02s01 |

### P1 — high (fix before merge)

| Scenario ID | Behavior | Level | Story |
|---|---|---|---|
| SC-e02s01-P1-01 | Command `goto` targets are only statically compiled nodes; a drifted label cannot crash mid-run (#1088 class) — asserted via typed `Command[Literal[...]]` + graph compile test | Integration | e02s01 |
| SC-e02s01-P1-02 | Config: unknown `debate_gate` value → clear validation error at config time; `TRADINGAGENTS_DEBATE_GATE` env overrides default | Unit | e02s01 |
| SC-e02s01-P1-03 | RM prompt variants: skipped-debate paragraph present **only** on skip; held-debate prompt unchanged (existing `test_structured_agent_prompts.py` stays green) | Unit | e02s01 |
| SC-e02s01-P1-04 | `create_initial_state` pre-initializes the new gate state field — bare programmatic states never KeyError (house rule) | Unit | e02s01 |
| SC-e02s01-P1-05 | `always`/`never` modes make **zero** LLM calls at the gate (call-counting fake) | Unit | e02s01 |
| SC-e02s02-P1-01 | `_run_signature` includes gate mode: resume under a different mode starts fresh; same mode resumes correctly (#1089 pattern, extend `test_checkpoint_lifecycle.py`) | Integration | e02s02 |
| SC-e02s02-P1-02 | CLI config precedence: env > saved prefs > default `auto`, matching `research_depth` handling (`test_cli_config_precedence.py` / `test_cli_env_skip.py` patterns) | Unit | e02s02 |

### P2 — medium

| Scenario ID | Behavior | Level | Story |
|---|---|---|---|
| SC-e02s01-P2-01 | Language independence: non-English analyst reports gate identically (structured verdict is language-agnostic; marker stays internal-English) | Unit | e02s01 |
| SC-e02s02-P2-01 | Live display on skip: Bull/Bear show `skipped`, never stuck `pending`; analyst status logic and wall-time tracker unaffected | Unit (fake buffer) | e02s02 |
| SC-e02s02-P2-02 | Report surface: saved report tree + CLI report display render the gate section in all three modes (skipped verdict / debate held N turns / disabled by configuration) | Unit (tmp_path) | e02s02 |
| SC-e02s02-P2-03 | Prefs: `debate_gate` persists round-trip; sanitize rejects invalid values (`test_cli_prefs.py` pattern) | Unit | e02s02 |
| SC-e02s03-P2-01 | User-facing docs exist: CHANGELOG announces default change + restore switch; `.env.example` documents the env var; README documents `debate_gate` | grep-gate (runnable) | e02s03 |

### P3 — low

| Scenario ID | Behavior | Level | Story |
|---|---|---|---|
| SC-e02s02-P3-01 | Gate verdict + rationale logged at INFO with the ticker context; failure path logs WARNING (never silent) | Unit (caplog) | e02s02 |
| SC-e02s03-P3-01 | specs knowledge refresh: tech-stack flow + glossary mention the Debate Gate | grep-gate | e02s03 |

## 2. Fixture Architecture & Isolation

- **Reuse, do not modify** the autouse fixtures in `tests/conftest.py` (`_dummy_api_keys`,
  `_isolate_config`) — the gate reads `debate_gate` from the global config, so
  `_isolate_config`'s deep-copy reset is what keeps mode leakage out of the suite.
- **Fake gate LLM** (new, in `tests/test_debate_gate.py`): object with
  `with_structured_output(schema)` returning a stub whose `.invoke(prompt)` yields a
  preset `DebateGateVerdict`, raises, or returns None; plain `.invoke` records calls so
  "zero LLM calls" is assertable. Extends the existing `mock_llm_client` conftest fixture
  pattern.
- **Graph fixture**: compile the real `GraphSetup` graph with all agent factories stubbed
  to no-op state writers (pattern: `_bare_graph` in `test_signal_processing.py`,
  `test_checkpoint_lifecycle.py`); capture visited-node order from `stream(mode="values")`.
- **Checkpoint fixture**: `tmp_path` data_cache_dir + SqliteSaver via the existing
  `checkpoint_scope` helpers (pattern: `test_checkpoint_resume.py`).
- **CLI fixture**: fake console/message buffer per `test_cli_display.py`; no questionary
  interaction — selections dicts are injected (pattern: `test_cli_commands.py`).
- **Isolation rules**: no network anywhere; every test sets `debate_gate` explicitly
  (never relies on the default) except the two default-value tests; report tests use
  `tmp_path` only.

## 3. NFR Verification

| NFR | Verifiable command |
|---|---|
| Gate adds ≤1 quick-LLM call in auto; 0 in always/never | `.venv/bin/python -m pytest -q tests/test_debate_gate.py -k "llm_calls"` |
| `always` mode is behavior-identical to current main (node sequence) | `.venv/bin/python -m pytest -q tests/test_debate_gate.py -k node_sequence` |
| No new runtime dependencies | `git diff --exit-code $(git merge-base HEAD main 2>/dev/null || echo HEAD) -- pyproject.toml \|\| grep -c "dependencies" pyproject.toml` — human review gate: pyproject dependency list unchanged |
| Suite stays green incl. new tests; lint clean | `.venv/bin/python -m pytest -q && ruff check .` |
| Traceability: every scenario referenced in test files | `grep -rc "scenario: SC-e02" tests/ \| grep -v ':0'` (≥1 file per story) + `# story: e02sNN` tags |

## 4. Out of Scope

- **Live judge quality** — whether a real LLM's tension judgments are *good* is model
  behavior, not code correctness; belongs to the deferred backtest A/B harness
  (SCOPE out_of_scope #5), not this suite.
- **Risk-debate gating** — deferred by decision; no tests for unwired behavior.
- **Debate-cost benchmarking** — no perf harness exists; economics tracked via call counts only.
- **Non-English judge prompt quality** — only the language-independence invariant is tested
  (SC-e02s01-P2-01), not translation quality.
