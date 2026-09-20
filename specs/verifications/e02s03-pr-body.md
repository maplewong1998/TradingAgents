# e02s03 — PR body (step 7 draft, committed on the branch)

```yaml
story: e02s03
epic: e02
branch: feat/e02s03
base: 276cfc4            # main tip at kickoff; delta reviewed = git diff 276cfc4..bc376b6
tip_at_draft: bc376b6
compare_url: https://github.com/maplewong1998/TradingAgents/compare/main...feat/e02s03
commits_reviewed: 14     # kickoff 787a829 + 13 story-range commits
diffstat: 17 files, +710 / -146 (of which product docs +151, one 13-line fix(cli) hunk, +78 test lines)
decision: Open PR (team-pr; gh absent — the user opens the compare URL)
landed: false
```

## Draft commit message (commit-message skill output)

This is the message a squash/merge landing should carry. The 14 branch commits are
already individually conventional and stay as they are; this is the landing subject.

```text
docs(specs): refresh the CHANGELOG, .env.example, README and specs knowledge for the
conditional debate gate

The default run behavior changed in e02s01/e02s02 (the Bull/Bear debate is now held
only when the analyst reports disagree), and this branch makes that discoverable
without reading code. All five frozen tasks are docs/records work.

- CHANGELOG.md gains a new "## [Unreleased]" section: the default-policy change, the
  exact restore switch (debate_gate=always), the gate's fail-safe direction, and the
  one-time checkpoint re-keying (gate=<mode> in the run signature means a thread
  written before the gate is not resumable and each affected ticker starts fresh once).
- .env.example documents TRADINGAGENTS_DEBATE_GATE=always|auto|never with the default.
- README.md documents debate_gate in the config example, adds "The debate gate"
  section (policy table, skip rule, fail-safe direction), the Debate Gate Policy step
  in the CLI walkthrough, and the run-signature paragraph in Checkpoint resume.
- specs/tech-architecture/tech-stack.md gains the Debate Gate node in the architecture
  flow and the gate term in the run-signature signal; GLOSSARY_LATEST.yaml gains
  Debate Gate, Alignment Marker and debate_gate policy; CONVENTIONS.md § File-Size
  Exceptions rows re-lock at the true sizes (cli/main.py 1276, trading_graph.py 652,
  agents/schemas.py 392 with the e02s01 re-export rationale); AGENTS.md's cli/** row
  drops 1460 for 1276.

Two ruled quick-fixes ride along, as separate commits:

- fix(cli): cli/gate_policy.py printed the TRADINGAGENTS_DEBATE_GATE override notice
  twice in one run — select_debate_gate and resolve_debate_gate both announced it.
  Only resolve_debate_gate announces it now; values and precedence are unchanged.
- chore: .gitignore covers tests/_tmp_cache/, the directory the suite's cache paths
  leave behind (BUG-2026-09-20-no-data-handling-nonhermetic-cache).

Tests: test(cli) covers the single env notice, the cancel/SystemExit branch of
ask_debate_gate, and the env-skip path.

Semantic-release implication (record hygiene, reasoned out loud): if this repo ran
semantic-release, the squash subject above is `docs` → no version bump, while the
branch as a whole carries a `fix(cli)` (patch) whose user-visible effect is already
written up under "## [Unreleased]"; the intended release is still the minor named by
the epic's `feat(graph)` work. It makes no difference here: this repo has no
release tooling (.github/workflows holds only ci.yml, no .releaserc, pyproject is
pinned 0.5.0), so no tag is driven by any subject — the honest type is `docs`
because documentation is the dominant outcome, and the fix + tests are carried in
the body rather than hidden behind a `fix` title that would overstate this branch.

Story: e02s03
```

## Draft PR title

```text
docs(specs): refresh the CHANGELOG, .env.example, README and specs knowledge for the conditional debate gate
```

## PR body

## Summary
<!-- bigpowers-provenance: agent-generated -->

- **Story e02s03, the final story of epic e02** (Conditional Bull/Bear Debate Gate).
  Docs + knowledge refresh: the debate is now conditional by default, and this branch
  makes the gate, its policy knob and the restore switch discoverable without reading
  code, while refreshing the project's long-term memory (tech-stack, glossary).
- **User-facing docs:** `CHANGELOG.md` gains a `## [Unreleased]` section that states
  the default-policy change, `debate_gate: "always"` as the exact pre-gate restore,
  the fail-safe direction (a gate that cannot judge holds the debate), and the
  **one-time checkpoint re-keying** — `gate=<mode>` joins the run signature, so a
  thread written before the gate is not resumable and each affected ticker starts
  fresh once. `.env.example` documents `TRADINGAGENTS_DEBATE_GATE=always|auto|never`
  with the default. `README.md` gains a config line, a **The debate gate** section
  (policy table, skip rule, fail-safe direction), the **Debate Gate Policy** step in
  the CLI walkthrough, and the run-signature paragraph under Checkpoint resume.
- **specs knowledge:** `tech-stack.md` architecture flow gains the **Debate Gate**
  node and the gate term in the run-signature signal (plus every stale metric the
  docs pass could re-derive); `GLOSSARY_LATEST.yaml` gains **Debate Gate**,
  **Alignment Marker** and **debate_gate policy** with code sources; `CONVENTIONS.md`
  § File-Size Exceptions re-locks at the true sizes and `AGENTS.md` drops the stale
  1460-line `cli/**` row.
- **Two ruled quick-fixes ride along as separate commits:** `fix(cli)` — the
  `TRADINGAGENTS_DEBATE_GATE` override notice printed **twice** in one run because
  both `select_debate_gate` and `resolve_debate_gate` announced it; only the latter
  announces it now, with values and precedence unchanged. `chore` — `.gitignore`
  covers `tests/_tmp_cache/`, the directory the suite's cache paths leave behind
  (`BUG-2026-09-20-no-data-handling-nonhermetic-cache`).
- **One queue item deliberately deferred:** the injectable reachability check stays a
  fix-bug backlog item (`BUG-2026-09-20-no-data-handling-live-vendor-probe`); it does
  not belong in a 3-BCP docs story.

### Gate evidence

| Gate | Result |
|------|--------|
| Frozen plan | 5/5 tasks `status: passing`; every task carried a runnable `verify:` |
| verify-work round 1 | **PASS 9/9 phases** |
| audit-code (gatekeeper) round 1 | **PASS 100/100**, hard sections code/test/security all PASS, 0 HIGH findings |
| gate round 2 (delta re-check) | **PASS 100/100**, docs/records-only delta, `e53ee9d..bc376b6` |
| Preflight at the reviewed tip | **1027 passed / 2 skipped / 88 subtests**, ruff clean, `validate-specs-yaml: OK` |
| Commits | 14/14 Conventional Commits, every one carrying a `Story: e02s03` trailer, zero co-authored-by footers |

## Test plan

- [x] `ps -eo pid,args | grep -E "[p]ython -m pytest" | grep -v "bash -c"` → empty, then
      `.venv/bin/python -m pytest -q && ruff check . && bash scripts/validate-specs-yaml.sh`
      → 1027 passed / 2 skipped / 88 subtests, ruff clean, specs valid (worktree `.venv`, serial)
- [x] `pytest tests/test_cli_env_skip.py tests/test_cli_prefs.py -q` → 25 passed (the three new tests + the env-skip path)
- [x] Task 1: `grep -qi 'debate gate' CHANGELOG.md && grep -q 'TRADINGAGENTS_DEBATE_GATE' CHANGELOG.md`
- [x] Task 2: `grep -q 'TRADINGAGENTS_DEBATE_GATE' .env.example`
- [x] Task 3: `grep -q 'debate_gate' README.md`
- [x] Task 4: `grep -q 'Debate Gate' specs/tech-architecture/tech-stack.md && grep -q 'debate_gate' specs/product/GLOSSARY_LATEST.yaml`
- [ ] **Human UAT (owner):** read the `## [Unreleased]` entry and confirm it tells a 0.5.x
      user everything they need (conditional default; `always` restores; checkpoints re-key once);
      skim README § *The debate gate* and § *Checkpoint resume* for the same story
- [ ] Landing decision (user Safety gate): merge commit to `main` locally, or keep the branch

## Landing dispatcher notes (for the orchestrator at landing)

- `origin/main` is ahead of the branch base (`276cfc4`) while this branch sits on it, so a
  textual merge of `specs/state.yaml` and `specs/agent-locks.yaml` would resolve wrongly:
  **both files take the BRANCH copy** (state step-8 record + closed e02s03 metrics; locks with
  e02s03 released), then re-stamp the post-landing `vcs`/`pr` facts on `main`.
- `progress.md` → **union chronologically**, root-latest last (root carries the orchestration
  logs including the gate-child-failure adjudication).
- `specs/fleet-agents.yaml` → keep **root's newer copy**, add a landing note.
- `specs/verifications/*` → **union**: root has `e02s03-verify-r1.yaml` and earlier evidence;
  the branch has `AUDIT-e02-e02s03.md` (both rounds), `e02s03-pr-body.md` and
  `e02s03-kickoff-baseline.yaml`.
