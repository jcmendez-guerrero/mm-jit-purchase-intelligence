# Internal service APIs (ownership)

The BFF only orchestrates. Each route below is owned by one service, uses audience-scoped service identities, re-checks roles, and is described by a JSON Schema in `packages/contracts/dto`. Existing routes are reused; new ones are marked.

| Service | Route (logical) | State | Notes |
|---|---|---|---|
| procurement | GET/PUT `/suppliers/{id}/terms` | Extend | Add fields; If-Match; as_of |
| procurement | GET/PUT `/product-suppliers/{variant}/{supplier}/terms` | New | Overrides, precedence, conflicts |
| procurement | GET/PUT `/config/policies/purchase`, POST `.../preview` | New | Supersedes `/service-levels` ownership (ADR-018) |
| procurement | GET/POST `/scenarios`, GET `/scenarios/{id}`, POST `.../promote`, GET `.../export` | New | Reuses allocation engine in no-write mode |
| procurement | PUT `/internal/users/{id}/roles` | Existing | Called by the BFF relay |
| procurement | GET `/summary/spend` | New | Proposed spend KPI |
| forecast | GET/POST `/imports`, GET `/imports/{id}/{preview,dry-run}`, PUT `.../mapping`, POST `.../{validate,activate,rollback}` | New | Streaming upload; parsing in job |
| forecast | GET/PUT `/config/parameters` | New | Allowed keys and ranges |
| forecast | GET `/runs`, GET `/variants/{id}`, GET `/accuracy` | New/Extend | `/forecasts/latest` retained |
| inventory | GET `/dashboard/{summary,demand-trend,abc-xyz,risks}`, GET `/filters/options` | New/Extend | `/dashboard/risk` retained |
| inventory | GET/PUT `/config/demand-rules` | New | Exclusions and censoring rules |
| api-bff | all routes in `bff-api.delta.openapi.yaml` | New | Roles stored in `bff` schema |
| siweb-connector, siweb-cost-writer | none | Unchanged | Tests assert no new path or method |
