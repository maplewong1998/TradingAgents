# Story e02s03: Docs + knowledge refresh

<!-- story: e02s03 -->

**type:** docs
**risk:** P2 (no behavioral change; discoverability of a default-behavior change)
**context:** domain
**bcps:** 3
**status:** done (e45s06 ledger — 5/5 tasks passing; the frozen file's ledger flips at story close)

**Context:** The default run behavior changes (debate becomes conditional under `auto`).
Users must be able to discover the gate, the policy knob, and the restore-old-behavior
switch (`always`) without reading code — and the project's long-term memory
(`specs/tech-architecture/tech-stack.md`, glossary) must reflect the new architecture.

## Requirements (delta tags, e45s29)

#### ADDED: User-facing documentation
CHANGELOG entry (feat(graph), announces the default change, the one-time checkpoint
signature churn, and `debate_gate=always` as the exact-behavior restore);
`.env.example` documents `TRADINGAGENTS_DEBATE_GATE=always|auto|never` with the default;
README configuration section documents `debate_gate` and the CLI prompt step, plus one
paragraph on when the debate is skipped and the fail-safe direction.

#### ADDED: specs knowledge refresh
`tech-stack.md` architecture flow gains the Debate Gate node (and its § Signals note on
`setup_graph` hardcoding is updated for the new node registration); `GLOSSARY_LATEST.yaml`
gains **Debate Gate**, **Alignment Marker**, **debate_gate policy** with code sources.

## Slopcheck

No packages. Docs only.

## Steps

1. CHANGELOG entry under the next release section, Conventional-Commits style → verify: `grep -qi 'debate gate' CHANGELOG.md && grep -q 'TRADINGAGENTS_DEBATE_GATE' CHANGELOG.md`
2. `.env.example` env var + comment → verify: `grep -q 'TRADINGAGENTS_DEBATE_GATE' .env.example`
3. README config + CLI walkthrough + skip/fail-safe paragraph → verify: `grep -q 'debate_gate' README.md`
4. tech-stack.md flow diagram + glossary terms → verify: `grep -q 'Debate Gate' specs/tech-architecture/tech-stack.md && grep -q 'debate_gate' specs/product/GLOSSARY_LATEST.yaml`
5. Full gates → verify: `.venv/bin/python -m pytest -q && ruff check . && bash scripts/validate-specs-yaml.sh`

## §17 Acceptance Criteria (Gherkin)

```gherkin
# scenario: SC-e02s03-P2-01
Given a user upgrading from 0.5.x
When they read the CHANGELOG
Then they learn the debate is conditional by default, checkpoints re-key once, and debate_gate=always restores prior behavior

# scenario: SC-e02s03-P3-01
Given the shipped gate
When an agent runs survey-context
Then tech-stack.md and the glossary describe the Debate Gate without re-reading source
```

## Verification Script (Step-by-Step, UAT)

1. Read the new CHANGELOG entry — confirm it names the default change, the env var, and the `always` restore switch.
2. `grep -n TRADINGAGENTS_DEBATE_GATE .env.example README.md` — both documented consistently.
3. `grep -n "Debate Gate" specs/tech-architecture/tech-stack.md specs/product/GLOSSARY_LATEST.yaml` — knowledge refreshed.
4. `.venv/bin/python -m pytest -q && ruff check .` — Preflight still green.

## Out of scope

- Blog/tutorial content; API docs site; risk-debate documentation (deferred feature).

## Risks

- **Doc drift** — README/config table and `.env.example` can diverge; step 5's greps pin
  the key names in both.
