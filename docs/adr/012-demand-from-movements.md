# ADR-012: Demand from stock movements

- Status: accepted
- Date: 2026-11-04

## Decision outcome
`demand = −Σ sale_shipment − Σ return_customer`, per variant, day and warehouse. Transfers, adjustments, damage, theft, expiry, counts, initial stock, production and supplier flows are excluded and kept as separate series; loss is never demand.

Loss classification uses a configurable reason cutover date (default 2026-09-19): before it every `adjustment_negative` is `unclassified_loss`; after it `expiry`/`damage`/`theft` are trusted and a missing reason is `unspecified_loss`. A data-quality metric shows the share of post-cutover negative adjustments without a structured reason.

Free-text notes are not parsed or stored (only `has_note`). Sale movements without a recognisable ticket or invoice reference are quarantined. Stock history is rebuilt backwards from the current snapshot; days at or below zero stock are censored.

Open detail: `reference_type` values (Gate 0, V2).
