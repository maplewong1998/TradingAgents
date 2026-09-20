---
okf_kind: story-metrics
okf_version: "0.1"
type: StoryMetrics
id: e02s01
epic: e02
bcps: 8
commit_range: "d7557e4..d7557e4"
source: measured
generated_at: 2026-09-20T07:34:42Z
generator: scripts/record-cycle-time.sh

# DORA — the four keys (market standard). ⌀ median aggregate.
dora:
  lead_time_for_changes_min: 0   # ⌀ first commit → merge
  deployment_frequency: null           # % populated by e40s05
  change_failure: null                   # % populated by e40s05
  time_to_restore_min: null              # ⌀ populated by e40s05

# Agent code-generation telemetry (GSD-2 style). Σ additive.
agent:
  cost_usd: null                         # Σ harness telemetry (null = git effort fallback)
  tokens:
    input: null
    output: null
    cache_read: null
    cache_write: null
    total: null
  cache_hit_rate_pct: null               # %
  compression_savings_pct: null          # %
  tool_calls: null                       # Σ
  api_requests: null                     # Σ
  agent_duration_ms: null                # Σ (excludes human UAT wait)
  model: null                            # •
  tier: null                             # • light|standard|heavy
  model_downgraded: null                 # •
  skills: []                           # Σ

# Effort (git-derived, idle-stripped, ADDITIVE).
effort:
  effort_hours: 0.0000              # Σ idle-stripped (git-hours, 120-min threshold)
  idle_threshold_min: 120              # • recorded for interpretability

# Quality gate. ⌀ median / • static.
quality:
  audit_score_pct: null                 # ⌀ populated by audit-code
  coverage_pct: null                    # ⌀ populated by test suite
  tests_passed: null                    # • populated by test suite
  verify_status: null                   # pass|waived
  rework_count: null                    # Σ reopens → feeds change_failure

# Flow (worktree telemetry).
flow:
  merge_duration_ms: null               # ⌀ p50/p95 across stories
  merge_conflicts: null                 # Σ
  worktree_orphaned: null               # •
---

# Story metrics — e02s01

Effort derived from git commit history via the git-hours model
(src: kimmobrunfeldt/git-hours, 120-min idle threshold, 120-min
first-commit pad). Lead time is calendar latency (first commit → merge).

Aggregation tags: Σ additive (sum → total) · ⌀ median/p95 (never sum)
· % rate (ratio over window) · • static (identity).
