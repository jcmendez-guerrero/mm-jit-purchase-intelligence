# Event Contracts (asynchronous)

Transport: Storage Queues behind a `MessageBus` interface (Azurite locally). Delivery is at-least-once; consumers deduplicate on `event_id` via inbox tables. Payloads are small, contain no secrets or personal data, and point to data through `payload_ref` (blob or API reference with `sha256` checksum). Schemas live in `packages/contracts/events/*.schema.json`, versioned in the type name.

## Envelope (all events)

| Field | Type | Notes |
|---|---|---|
| event_id | uuid | Dedup key |
| type | string | e.g. `siweb.sync.completed.v1` |
| schema_version | string | Semver of the payload schema |
| occurred_at | RFC 3339 UTC | |
| correlation_id | uuid | Propagated across the whole flow |
| resource_id | string | Primary resource affected |
| payload_ref | object | `{uri, sha256}`; validated against the schema before processing |

## Events

| Type | Producer → consumers | Trigger |
|---|---|---|
| siweb.sync.completed.v1 | siweb-connector → inventory-service | A reconciled sync run commits |
| inventory.snapshot.created.v1 | inventory-service → forecast-service, procurement-service | New stock snapshot projected |
| inventory.demand.updated.v1 | inventory-service → forecast-service | Demand/flow series rebuilt |
| forecast.completed.v1 | forecast-service → procurement-service | Forecast/policy run finished |
| procurement.proposal.generated.v1 | procurement-service → api-bff (notification) | Weekly proposal ready |
| procurement.order.confirmed.v1 | procurement-service → inventory-service (inbound projection) | Buyer confirms a supplier order |
| procurement.cost.write_requested.v1 | procurement-service → siweb-cost-writer | Buyer approved a pending cost write |
| siweb.cost.write_completed.v1 | siweb-cost-writer → procurement-service | Write succeeded or failed (outcome in payload) |

## Rules

- **Fan-out**: producer outbox relay writes one message per subscribed queue.
- **Authenticity**: per-queue Sender/Processor RBAC with managed identities; consumers reject messages whose schema or checksum fails validation.
- **Freshness**: messages older than the configured window (default 24 h, 1 h for `procurement.cost.write_requested.v1`) are rejected and alerted.
- **Retry**: bounded exponential backoff, then poison queue + alert.
- **Compatibility**: additive changes bump minor; breaking changes need a new type version (`.v2`) with parallel support during rollout and contract tests on both sides.
- **Write safety**: `procurement.cost.write_requested.v1` must reference an existing `cost_write_request` in status `approved_by_buyer`; the writer re-checks this through the procurement API (service identity) before calling Siweb, so a forged message cannot trigger a write.
