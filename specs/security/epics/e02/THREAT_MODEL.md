# THREAT MODEL — epic e02 (Conditional Bull/Bear Debate Gate)

<!-- build-epic step 0 artifact — produced at step 2 because the epic had none (2026-09-20) -->
<!-- scope: e02s01 (landed d7557e4) + e02s02 (this story) + e02s03 (docs) -->

- **Epic risk:** **LOW–MEDIUM** — no new attacker-facing trust boundary, no credentials,
  no network listener. The epic changes *which agents run* on a trading-research run and how
  that decision is shown and persisted.
- **Owner:** resident `story_ops` (step 2 of story e02s02); consumed by `plan-work` `security:`
  fields, `verify-work` phase 5, and `audit-code`.
- **Evidence base:** `AUDIT-e02-e02s01.md` (0 HIGH, 0 MED, 1 standing LOW after round 2),
  `specs/tech-architecture/IMPACT_LATEST.md:48`, and the code cited below.

## 1. Surface area

| Surface | Where | Reachable by |
|---|---|---|
| Judge prompt interpolates the four analyst reports (news / social / fundamentals text) | `tradingagents/agents/gate/debate_gate.py:117-136` via `report_or_absent` | External web/news content, indirectly (#1176 class) |
| Gate routing decision (`Command(goto=...)`) | `debate_gate.py:78-168`, static `Literal` targets | Config value `debate_gate` (env / prefs / CLI) |
| Gate policy input | `TRADINGAGENTS_DEBATE_GATE` → `debate_gate` (`default_config.py:20,79-81,143`); validated again at graph init (`trading_graph.py:90-93`) | Env var, `~/.tradingagents/cli_prefs.json`, interactive prompt (e02s02) |
| Gate decision record `debate_gate_verdict` | `agent_states.py:73`, written at `debate_gate.py:88,160,184,201,222` | Persisted in state + checkpoint + saved reports (e02s02) |
| Saved report tree | `tradingagents/reporting.py:13-101`; path built with `safe_ticker_component` (`trading_graph.py:513-515`) | Local filesystem |
| CLI live display (Rich markup) | `cli/main.py:306-380` (status cells), `:788-848` (complete report) | Terminal |
| Checkpoint thread identity | `_run_signature` (`trading_graph.py:399-413`) → `thread_id` | Local sqlite checkpoint store |

**Trust boundaries:** unchanged by this epic. The gate reads state that every downstream agent
already reads and calls the same configured quick LLM through the existing
`bind_structured` boundary (`agents/utils/structured.py`). No new auth, crypto, SQL, subprocess,
deserialization, or file-upload surface is introduced.

## 2. Vulnerability categories assessed

| Category (CWE) | Assessment | Where |
|---|---|---|
| Prompt injection → decision manipulation (CWE-1427 / #1176 class) | **Bounded LOW.** Analyst reports embed external content that is interpolated into the judge prompt. A skip requires a pydantic-validated `DebateGateVerdict` with `evidence_aligned=True`, `confidence != "low"` and a definite direction (`debate_gate.py:148-166`); worst case is reduced deliberation depth — RM, Trader, risk debate and PM all still run, and the verdict + rationale are persisted for audit. Any judge anomaly fails **into** the debate (`_fail_safe`, `debate_gate.py:212-224`). | `debate_gate.py:107-146` |
| Fail-open routing on unknown/missing policy (CWE-754) | **Mitigated.** Unknown mode → explicit `ValueError` at config build (`default_config.py:79-81`) and at graph init (`trading_graph.py:90-93`); in-node drift fallback holds the debate (`debate_gate.py:100-104`); missing structured support holds the debate (`:106-107`). No silent "behaves like auto". |
| Verdict fabrication on the policy path (CWE-1188 misconfiguration shown as data) | **Fixed in e02s01 round 2.** `never` mode renders `render_policy_skip_marker` (`gate/schemas.py:75-91`), which states no judge was consulted — it no longer claims an alignment finding. Pinned by `tests/test_debate_gate.py`. |
| Checkpoint integrity — resuming a graph the run was not built for (CWE-345 class integrity control) | **Open until e02s02 task 1.** The gate node + rerouted edge changed graph shape at `d7557e4` while `_run_signature` (`trading_graph.py:406-413`) still omits the policy: a pre-gate thread and today's threads share a signature, and two policy modes share one signature. Mitigation: add `gate=<mode>` (task 1), pinned by SC-e02s02-P1-01. |
| Report/display injection via LLM text (CWE-79 analogue, terminal/markdown sink) | **LOW, new in e02s02.** The gate rationale is LLM-authored text. Written to markdown (`reporting.py`) it is inert; rendered in the CLI through Rich, markup in an `f"[...]{value}[/...]"` string is *interpreted* (see `cli/main.py:344-373` for the existing pattern) — a rationale containing `[red]`-style markup could spoof styling. No code execution, no data exfiltration. Mitigation: pass untrusted text through `Markdown`/`Text` objects rather than markup-formatted f-strings; keep status strings internal constants (`skipped`). |
| Path traversal on report output (CWE-22) | **Mitigated (pre-existing).** Ticker-derived paths go through `safe_ticker_component` (`trading_graph.py:513-515`); `write_report_tree` only mkdirs and writes under the given `save_path`. e02s02 adds a section, not a sink. |
| Secrets exposure (CWE-532) | **No new exposure.** The gate logs only `verdict.rationale` and config reasons (`debate_gate.py:181,198,216`); prompts are never logged; no API key material in the diff. |
| Dependency supply chain (CWE-1395) | **None.** Frozen spec §Slopcheck: no new packages; `questionary`/`rich` already pinned. |

## 3. Risk level per story

| Story | Risk | Rationale |
|---|---|---|
| e02s01 (done) | **Medium** — gate changes what the pipeline runs; bounded by fail-safe routing + rating-integrity pins. Gate audit: 0 HIGH, 0 MED. |
| e02s02 | **Low–Medium** — user-visible display/report wording and checkpoint identity. No new trust boundary; the one integrity control (signature) is additive. |
| e02s03 | **Low** — documentation only. |

## 4. Mitigation guidance for the `security:` task field

Frozen e02s02 tasks carry no `security:` field (pre-freeze artifacts, not rewritten at step 2).
Applying this model: **task 1 → `low`** (checkpoint integrity), **tasks 2–4 → `low`** (input is a
validated `Literal` mode and LLM-authored text rendered into local surfaces), **tasks 5–6 → `none`**.
They are not gate conditions:

- Any task touching `reporting.py` or the CLI report/display path must state in its verify that
  **no new security findings appear in the affected paths** and that the rendered section contains no
  raw-mode markup injection from rationale text.
- No task may delete or weaken `_fail_safe` / the confidence guard / the `Literal` target set.

## 5. Open items

- No `specs/security/EXCEPTIONS.md` is needed: 0 open HIGH findings.
- Standing: one LOW (bounded prompt-injection surface on the judge) accepted by design in
  `AUDIT-e02-e02s01.md:74`.
- This threat model is additive — it does not modify the frozen e02s02 spec or tasks.
