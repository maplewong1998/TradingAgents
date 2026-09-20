# e01s02 — Seed AGENTS.md and CONVENTIONS.md

<!-- story: e01s02 -->

**Status:** done — 2026-09-20
**Epic:** e01 Bigpowers Adoption

## Intent

Before this story the repo had no agent instruction file, so each tool
(Claude Code, Cursor, OpenCode, Cline) had to be told the conventions ad hoc.
The repo already enforces a strong house style in `pyproject.toml` (ruff rule
selection, line length, test markers) and in its test harness — that intent was
never written down in one place.

## Acceptance

- `AGENTS.md` follows the bigpowers Reach Template, with the filled Commands,
  Architecture, Conventions, Never, and Agent Rules sections.
- `CLAUDE.md` resolves to the same content.
- `CONVENTIONS.md` embeds the Always Green / Shift Left and Discovered Defects
  doctrine, the banned-dismissive-phrases table, and the risk tiers.
- Recorded commands are real and runnable in this repo.

## Verify

```bash
test -f AGENTS.md && test -e CLAUDE.md && test -f CONVENTIONS.md
grep -q 'Always Green' CONVENTIONS.md
grep -q 'Discovered Defects' CONVENTIONS.md
```

## Outcome

Delivered. Commands were taken from `pyproject.toml` (`[tool.pytest.ini_options]`,
`[tool.ruff]`) and from the `tradingagents` console script, so the Preflight row
is executable as written.
