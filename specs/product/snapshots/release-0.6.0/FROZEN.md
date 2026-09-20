# FROZEN — release-0.6.0 planning baseline

**Frozen:** 2026-09-20 (user directive: "Stop and freeze the plan before develop-tdd")
**Frozen at commit:** 34085c8 (`chore(specs): bigpowers planning artifacts — e01 bootstrap, e02 debate-gate epic`)
**Branch:** `feat/e02-conditional-debate-gate` (kickoff-branch complete, Preflight green: 946 passed / 2 skipped / ruff clean)
**Implementation status:** NOT STARTED — no e02 code or tests exist; all task ledgers are `status: failing`.

## What is in this snapshot

Doctrine requires the release trio (`release-plan.yaml`, `SCOPE_LATEST.yaml`,
`VISION_LATEST.yaml`) at planning close. This snapshot **extends** that with the full
e02 plan baseline so the freeze is self-contained — everything `develop-tdd` would
consume, immutably captured:

| Path | Role |
|---|---|
| `release-plan.yaml`, `SCOPE_LATEST.yaml`, `VISION_LATEST.yaml` | Doctrine trio (planning close) |
| `epics/e02-conditional-debate-gate/` | Epic manifest, 3 story specs, 3 failing-ledger tasks.yaml |
| `tech-architecture/e02-TEST_PLAN_LATEST.md` | 16 test scenarios (SC-e02sYY-P*-NN) |

## Freeze rules

- These copies are **read-only history**. Never edit files under this directory.
- Work proceeds against the **live** artifacts in `specs/epics/` and
  `specs/tech-architecture/`. If a live artifact must diverge from this baseline
  (scope change, re-slice), that is a `change-request` — record the reason in the
  live artifact and re-freeze a new snapshot; do not silently drift.
- At merge, diff live vs. frozen to audit plan drift:
  `diff -r specs/product/snapshots/release-0.6.0/epics/e02-conditional-debate-gate specs/epics/e02-conditional-debate-gate`

## Resuming

1. Re-acquire the e02s01 lock in `specs/agent-locks.yaml` (released at freeze).
2. Set `metrics.story_start` and `active_flow: execute` in `specs/state.yaml`.
3. Run `develop-tdd` on `specs/epics/e02-conditional-debate-gate/e02s01-tasks.yaml`
   (tasks 1–9, two-commit RED/GREEN discipline per e45s08).
