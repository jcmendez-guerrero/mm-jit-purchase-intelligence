# ADR-021: Contract versioning and deprecation

- **Status:** accepted (clarification session 2026-11-08, spec 005)
- **Context:** Parallel domain agents depend on shared schemas in `packages/contracts`. An in-place breaking change would break consumers that other agents are still building.
- **Decision:** Shared interfaces are frozen at a version. A compatible change (only added optional properties) may edit the schema and refresh the baseline. A breaking change adds `name.v2` next to `name.v1`; v1 is marked `deprecated` with `superseded_by` and stays until every consumer listed in `docs/architecture/integration/contract-matrix.json` has moved to v2. Changes go through Agent 00 and are recorded in the matrix. The contracts gate enforces this.
- **Consequences:** Two versions may coexist for a while, so consumers are tracked in the matrix. Constitution Principle IV and its migration rule are satisfied. Alternatives rejected: in-place change with synchronized consumers (blocks parallel work); additive-only (too rigid).
