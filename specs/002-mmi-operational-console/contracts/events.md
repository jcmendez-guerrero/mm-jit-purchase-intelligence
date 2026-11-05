# Event changes for MMI 002

Same transport, envelope, fan-out, authenticity, freshness, retry and compatibility rules as `specs/001-mmi-purchase-intelligence/contracts/events.md`. All new types are `.v1`; schemas go in `packages/contracts/events` first.

| Type | Producer → consumers | Trigger |
|---|---|---|
| forecast.seed.activated.v1 | forecast-service → forecast-service worker, api-bff (notification) | Dataset activated or rolled back; requests a versioned run |
| forecast.completed.v1 | forecast-service → procurement-service | Existing; payload gains `dataset_version_id`, `parameter_version_ids` (additive, minor bump) |
| procurement.terms.changed.v1 | procurement-service → api-bff (notification) | New terms/policy version saved |
| procurement.scenario.ready.v1 | procurement-service → api-bff (notification) | Scenario computed |
| bff.roles.changed.v1 | api-bff outbox relay → procurement (via authenticated internal call, not a queue) | Role assignment saved; retried until acknowledged |
| inventory.rules.changed.v1 | inventory-service → forecast-service | Exclusions or censoring rules changed; may trigger re-forecast on request |

Every message is idempotent on `event_id`; none carries file contents, quantities per product or personal data (references only).
