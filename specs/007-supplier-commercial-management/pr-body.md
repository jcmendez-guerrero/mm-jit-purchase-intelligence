## What and why

Supplier Commercial Management (Jira MMI-6, Confluence page 3080407, epic MMI-1), Spec Kit feature `specs/007-supplier-commercial-management/`. Tasks T001–T050 in that `tasks.md`.

Acceptance: CRUD persists; effective dates and revision conflicts are handled; the optimizer consumes the local terms; Siweb canonical facts are unchanged.

Added on top of the audit of features 002/004: idempotent term saves (`Idempotency-Key`), expected delivery date from the order schedule and cutoff, per-row bulk-assign outcomes, ERP-vs-manual cost difference, non-EUR suppliers through stored ECB rates (ADR-021), audit of refused changes, and a block on approving a proposal that uses a deactivated supplier.

## Checklist

**Data**
- [x] Synthetic fixtures only (`packages/testing/fixtures/fx/ecb_rates.v1.json` has the real response shape with invented values)
- [x] Tax ids, bank details and note text are refused (422), never stored; only `has_note` exists (`test_supplier_privacy.py`)

**Security**
- [x] No secrets or real identifiers. No new Siweb request type; the only new outbound call is the public ECB rate feed (`https://api.frankfurter.dev/v2/providers/ecb/rates?base=EUR`, fixed URL, no credentials)
- [x] Refused changes are audited without the request body, bounded: no valid sign-in is counted not stored, identical refusals collapse to one entry per minute with a repeat count, the write runs off the event loop, the 256 KB limit holds for every content type, and the rate-feed read stops at its limit (review fixes, FR-038 to FR-041); the BFF cost override now also needs a fresh second factor (gap found by T044)

**Cost**
- [x] No new always-on resource. One rate fetch about daily inside the existing procurement worker (`MMI_FX_DISABLED=1` turns it off); two small tables (`terms_idempotency`, `fx_rates`, purged at 400 days)

**Contracts**
- [x] New error codes (`idempotency_key_reuse`, `invalid_idempotency_key`, `fx_rate_missing`, `fx_rate_stale`, `proposal_has_deactivated_supplier`, `payload_too_large`) are in the catalogue, Spanish texts and the 002 key table; optional `explanation.terms.expected_delivery_date` added to the proposal line schema
- [ ] Agent 00 sign-off on the shared contract changes (T003) is still pending

**Quality**
- [x] Procurement 798+, BFF 177, contracts 208, infra 59, connector 125, writer 66, web 495 unit tests pass; Playwright supplier journeys pass; ruff, eslint and tsc clean; migrations run and reverse on real PostgreSQL
- [x] All user-facing text is Spanish through the catalogue
- Not a merge or deploy request.
