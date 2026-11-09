@AGENTS.md

# Claude Code notes

- Spec Kit workflow: `/speckit-*` skills in `.claude/skills`; feature directory is recorded in `.specify/feature.json`.
- Run tests with synthetic fixtures only; never fetch from a real Siweb host.
- Prefer small, task-sized changes and update `specs/001-mmi-purchase-intelligence/tasks.md` as tasks complete.
- Shared contracts, the audit, the integration plan and the release gates live in `docs/architecture/integration/`; run `python -m gates run` from `scripts/` before opening a PR that touches `packages/contracts` or service schemas.
