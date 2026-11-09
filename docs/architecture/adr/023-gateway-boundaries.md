# ADR-023: Gateway orchestrates, domains own business rules

- **Status:** accepted (spec 005, Confluence scope for Agent 00)
- **Context:** The gateway (`services/api-bff`) composes calls across domains. Business rules placed there would duplicate or bypass the domain services and the schema ownership in ADR-018.
- **Decision:** The gateway only authenticates, authorizes, composes and forwards; every business rule lives in the owning domain service. Mutations carry idempotency keys and take effect once. The gateway owns only its `bff` schema (durable roles). Shared gateway endpoints are listed in the contract matrix (kind `endpoint`) with Agent 00 as owner, and cross-domain behaviour is covered by integration tests under `infra/tests`.
- **Consequences:** A review of `services/api-bff` for business rules is part of the work (`docs/architecture/integration/gateway-review.md`); findings that belong to other agents are reported, not moved. Rejected: letting the gateway cache or derive business values (drift and hidden rules).
