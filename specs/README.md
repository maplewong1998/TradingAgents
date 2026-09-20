# specs/README.md

All planning documents for TradingAgents live here. `specs/` is the project's
long-term memory: every skill that produces written output writes into this tree.

Read `state.yaml` first — it is the cockpit for "where are we right now".

## Layout

| Path | Answers |
|------|---------|
| `state.yaml` | Session cockpit: active flow, epic/bug, git, `handoff.next_skill`, metrics |
| `release-plan.yaml` | What ships in this release, in what WSJF order (mirror — tags are authoritative) |
| `execution-status.yaml` | Flat `e01` / `e01s01` status keys — sole source of truth for story state |
| `planning-status.yaml` | Discover-phase checklist (optional) |
| `metrics/cycle-times.yaml` | Per-story cycle-time ledger |
| `product/SCOPE_LATEST.yaml` | What is in and out of scope |
| `product/VISION_LATEST.yaml` | North star / initiative framing |
| `product/GLOSSARY_LATEST.yaml` | Ubiquitous language, derived from the code |
| `product/snapshots/` | Frozen release plans, copied at planning close |
| `tech-architecture/tech-stack.md` | Stack, architecture, observed conventions, signals |
| `tech-architecture/*_PLAN_LATEST.md` | Security, test, design, refactor, impact plans |
| `adr/` | Architecture decision records |
| `epics/` | Epic capsules (`epics/eNN-slug/`), archives in `epics/archive/` |
| `bugs/` | `BUG-*.md` investigations + generated `registry.yaml` |
| `verifications/` | Verification-gate artifacts |

## Validation

```bash
bash scripts/validate-specs-yaml.sh    # real YAML parse + required cockpit keys
```

## Related project context

- `AGENTS.md` — canonical agent context (Claude Code and Cursor read it via the `CLAUDE.md` symlink)
- `CONVENTIONS.md` — commit, git, workflow, and code conventions
