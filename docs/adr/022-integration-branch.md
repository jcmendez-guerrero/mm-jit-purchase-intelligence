# ADR-022: Integration branch, drop-and-continue and agent auto-fix

- **Status:** accepted (clarification sessions 2026-11-08 and 2026-11-09, spec 005)
- **Context:** Agent 00 must verify that the domain PRs work together but may not merge to main.
- **Decision:**
  - Agent 00 builds a temporary integration tree from main and each PR head (`python -m gates integrate`), locally or inside a manually started CI workflow. The tree is discarded; nothing is pushed.
  - Per-PR gates `contracts` and `isolation` are required checks on every PR. All six gates are required on the integration run.
  - A PR that fails a gate, conflicts, or touches paths it does not own is dropped together with the PRs that depend on it, and the run continues with the rest.
  - The gate report is saved as a CI artifact and summarized as a comment on each domain PR, with no new service. Each domain agent watches its own PR's result and automatically attempts fixes within its owned files; a fixed PR re-enters only after it passes. Auto-fix never merges to main, edits another agent's files or writes to the ERP.
  - Trust boundary: the job that runs merged PR code has read-only permissions; a separate job holds the comment permission, runs only trusted code from the default branch, takes the plan from there and treats the downloaded report as untrusted data (the summary strips mentions, links and HTML).
  - The maintainer merges the PRs to main in the documented order.
- **Consequences:** One bad PR does not block independent work; dependents stay blocked. Rejected: verifying PRs one at a time (misses interactions); stopping on the first failure; a bot service (cost, attack surface); pushing an `integration/*` branch.
