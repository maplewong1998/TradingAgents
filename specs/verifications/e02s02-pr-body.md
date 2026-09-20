# e02s02 — PR record (build-epic step 7, `commit-message`)

<!-- story: e02s02 -->
<!-- gh is not installed on this workstation: no PR object could be created. This file is the
     drafted title + body, ready to paste, and the compare URL to open it from. -->

**Compare URL:** https://github.com/maplewong1998/TradingAgents/compare/main...feat/e02s02
**Branch:** `feat/e02s02` (pushed, never force-pushed; `main` untouched)
**semantic-release bump:** **minor** (`feat`; no `!` marker, no `BREAKING CHANGE:` footer)
**Landing message (squash subject + body):**

```
feat(cli): add the debate-gate policy step and skipped-debate surfaces

Make the conditional debate safe to resume and visible while it runs.

The gate policy joins the checkpoint run signature, so a thread created under
one policy can never resume under another (#1089 pattern; graph shape is encoded
in three places, specs/tech-architecture/IMPACT_LATEST.md).

The CLI now offers the policy next to Research Depth (auto by default), remembers
it, and honours TRADINGAGENTS_DEBATE_GATE over the interactive answer with a
"(set by …)" notice. A debate the gate skips shows Bull/Bear as `skipped`
instead of leaving them `pending`, and both the saved report tree and the
complete-report display carry a Debate Gate section that says whether the debate
was held (with its turn count) or skipped and why.

Skip vs held is read from the debate transcript, never from the
`debate_gate_verdict` marker: the held path writes that key too, with the same
sentence, so neither its presence nor its text can discriminate.

New CLI code lands in cli/gate_policy.py, cli/stream_handler.py and
cli/complete_report.py because cli/main.py is at its file-size cap
(1460 -> 1276, extracted rather than grown).

Story: e02s02
```

---

## PR title

`feat(cli): add the debate-gate policy step and skipped-debate surfaces`

## PR body

```markdown
## Summary
<!-- bigpowers-provenance: agent-generated -->

Makes the e02s01 Debate Gate safe across **resumed** runs and visible to
**interactive** users. Story e02s02, 5 BCPs, risk P1, delta MODIFIED.

- **Checkpoint policy keying.** `gate=<mode>` joins `TradingAgentsGraph._run_signature`
  (`tradingagents/graph/trading_graph.py`), so a resume under a different gating policy
  starts fresh instead of continuing the wrong graph (#1089). This is the third encoding
  point of graph shape required by `specs/tech-architecture/IMPACT_LATEST.md:48`.
- **CLI policy step.** `cli/gate_policy.py` adds step 5b (Auto — recommended / Always /
  Never), persists the answer through `cli/prefs.py` (allowlisted + sanitized against
  `DEBATE_GATE_MODES`), and gives `TRADINGAGENTS_DEBATE_GATE` precedence with the same
  "(set by …)" notice pattern as research depth (#977).
- **Skipped-debate visibility.** `cli/stream_handler.py` maps a skip to a `skipped`
  terminal status for Bull and Bear (no agent is left `pending` or spinning) and
  `cli/complete_report.py` + `tradingagents/reporting.py` render a **Debate Gate**
  section: the judge's rationale when the gate skipped, `held (N turns)` when the debate
  ran, and the configuration marker when the policy disabled it.
- **Skip vs held is transcript-derived.** The held path also writes `debate_gate_verdict`
  (with the same "Debate skipped by the Debate Gate" sentence), so the surfaces classify
  from `investment_debate_state` (histories + turn count), never from that key — the drift
  finding ruled at plan time.
- **Never-silent logging.** Gate decisions log at INFO naming the instrument; failures keep
  logging WARNING (`tradingagents/agents/gate/debate_gate.py`).
- **File-size caps respected.** New CLI code went into new modules; `cli/main.py` shrank
  1460 -> 1276 (its §File-Size-Exceptions row is now stale — routed to e02s03).
- **Discovered defect.** `fix(tests): stub the live outage probe in TestLoadOhlcvNoPoison`
  (`7aae193`, quick-fix, BUG-2026-09-20-no-data-handling-live-vendor-probe) shipped
  separately on this branch, with its BUG spec and registry entry.

### Verification

| Gate | Result |
|---|---|
| Preflight at the reviewed tip (worktree venv, serial) | 1024 passed / 2 skipped / 88 subtests, `ruff check .` clean |
| verify-work | PASS 9/9 phases, round 2 (`specs/verifications/e02s02-verify-r2.yaml`); round 1 failed one phase (SC-e02s02-P3-01 INFO half) and was fixed |
| audit-code --gate | PASS 100/100, hard sections all PASS, 0 HIGH / 0 MED security findings (`specs/verifications/AUDIT-e02-e02s02.md`) |
| traceability | 0 dark, 0 orphan (`specs/TRACEABILITY_LATEST.md`) |
| Commits | all conventional, 17 story commits, `Story: e02s02` trailers, no AI-attribution footers |

Scenario coverage: SC-e02s02-P1-01, P1-02, P2-01, P2-02, P2-03, P3-01.

## Test plan
- [ ] Automated: `.venv/bin/python -m pytest -q && ruff check .` (expect 1024 passed, 2 skipped)
- [ ] Interactive (needs a provider key): `python -m cli.main`, accept Auto at the new step 5b
      prompt, analyse a ticker with clearly aligned signals — the research panel must show
      Bull/Bear as `skipped` and the report must carry the Debate Gate rationale
- [ ] Re-run with `TRADINGAGENTS_DEBATE_GATE=always` — the env notice replaces the prompt
      choice and the full debate runs (Debate Gate section reads `held (N turns)`)
- [ ] Re-run with `TRADINGAGENTS_DEBATE_GATE=never` — the section says the debate was
      skipped by configuration and that no judge was consulted
- [ ] Resume check: run with `--checkpoint`, interrupt, resume under a different policy —
      the run must start fresh rather than continue the old thread

## Known follow-ups (routed, not blocking)

- `CONVENTIONS.md` cap-table row `cli/main.py | 1460` is stale (actual 1276) → e02s03.
- Double env notice on the interactive path (`cli/gate_policy.py:76-81` and `:99-104`) → e02s03 polish.
- `tests/_tmp_cache` gitignore/ban and the injectable reachability check → e02s03 / quick-fix.
- The `ask_debate_gate` `SystemExit` branch is untested.
```
