# Internal service APIs (ownership)

The BFF only orchestrates. Each route below is owned by one service, uses audience-scoped service identities, re-checks roles, and is described by a JSON Schema in `packages/contracts/dto`. Existing routes are reused; new ones are marked.

| Service | Route (logical) | State | Notes |
|---|---|---|---|
| procurement | GET/PUT `/suppliers/{id}/terms` | Extend | Add fields; If-Match; as_of |
| procurement | GET/PUT `/product-suppliers/{variant}/{supplier}/terms` | New | Overrides, precedence, conflicts |
| procurement | GET/PUT `/config/policies/purchase`, POST `.../preview` | New | Supersedes `/service-levels` ownership (ADR-018) |
| procurement | GET/PUT `/config/stocking/{variant}`, GET/POST `/config/policy-overrides`, POST `.../{id}/{approve,reject,revert}` | New | Always-stocked floor; recommended vs effective safety stock; override requests with approval |
| inventory | GET `/products/{variant}/segment-history` | New | Category change history with reasons |
| procurement | GET/POST `/scenarios`, GET `/scenarios/{id}`, POST `.../promote`, GET `.../export` | New | Reuses allocation engine in no-write mode |
| procurement | PUT `/internal/users/{id}/roles` | Existing | Called by the BFF relay |
| procurement | GET `/summary/spend` | New | Proposed spend KPI |
| forecast | GET/POST `/imports`, GET `/imports/{id}/{preview,dry-run}`, PUT `.../mapping`, POST `.../{validate,activate,rollback}` | New | Streaming upload; parsing in job |
| forecast | GET/PUT `/config/parameters` | New | Allowed keys and ranges |
| forecast | GET `/runs`, GET `/variants/{id}`, GET `/accuracy` | New/Extend | `/forecasts/latest` retained |
| inventory | GET `/dashboard/{summary,demand-trend,abc-xyz,risks}`, GET `/filters/options` | New/Extend | `/dashboard/risk` retained |
| inventory | GET/PUT `/config/demand-rules` | New | Exclusions and censoring rules |
| procurement | GET/PUT `/costs/lots`, GET `/costs/{id}/median`, POST `/costs/{id}/override` | New | Lot-cost ledger and correction, median with its entries, margin check, admin override |
| inventory | GET `/lots/in-stock?variant=` | New | Lots of a variant with remaining quantity (inventory does not know suppliers); procurement matches them to its own per-supplier entries by variant and lot; called by procurement with an audience-scoped service identity when building a cost-update request |
| inventory | PUT `/products/{id}/criticality` | Existing | Reused by the policy console |
| api-bff | all routes in `bff-api.delta.openapi.yaml` | New | Roles stored in `bff` schema |
| siweb-connector, siweb-cost-writer | none | Unchanged | Tests assert no new path or method |

## Reconciliation with existing BFF routes (T013)

| Existing route (PR #1) | Decision |
|---|---|
| `GET /dashboard/risk` | Kept and extended (pagination, shared filters, drill-down keys). The proposed `/dashboard/risks` is dropped to avoid a duplicate. |
| `GET /suppliers`, `PUT /suppliers/{id}/terms` | Kept. PUT gains the extra term fields and `If-Match`; `GET /suppliers/{id}/terms` is new. |
| `GET/PUT /config/service-levels` | Kept as a compatibility alias; the policy console's purchase section absorbs it once the single owner is decided (T006). |
| `PUT /config/loss-cutover` | Unchanged. |
| `GET /costs`, `POST /costs/import`, `GET /cost-writes`, `POST /cost-writes/{id}/approve` | Unchanged; the cost-write review screen gains the median, lots and margin data (US3). |
| `/admin/roles` (`admin_roles.py`) | Kept; storage moves to the `bff` schema (US1), routes unchanged. |
| `GET/PUT/POST /proposals...` | Unchanged; proposals gain version references and the scenario link. |
