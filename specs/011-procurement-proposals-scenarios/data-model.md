# Data Model: Procurement Proposals & Scenarios

No new tables are planned. This lists the existing entities this feature relies on and the rules the tests assert. Tables live in the procurement-owned schema (`services/procurement-service/src/db/tables.py`).

## Proposal

- Fields: id, week, status, version (integer, incremented on every edit), created_by, last_edited_by, submitted_at, updated_at, input and rule versions.
- States: `draft` → `submitted` → `approved` (or back to `draft` on rejection or on any edit); `approved` → `exported` is a derived marker; `superseded` is set when a promoted scenario creates a newer proposal for the same week.
- Rules: approver is neither creator nor last editor; an edit after submission resets to draft and clears approval; a superseded proposal is read-only and cannot be edited, submitted, approved or exported.

## Proposal line

- Fields: id, proposal_id, variant_id (internal), sku (shown to users), supplier_id, qty, unit cost and source, pack, lead time, explanation, risk, confidence, constraint flags (minimum order, pack rounding, shipping, budget, shortfall).
- Rules: edits carry the expected proposal version; a stale version is rejected with `proposal_line_conflict` (the existing `version_conflict` stays for other uses); money is exact decimal.

## Scenario

- Fields: id, name, parameters (supplier deltas, budget cap, exclusions), status (`computing`, `ready`, `failed`, `promoted`), input_versions, result_hash, created_by, created_at.
- Rules: running the same parameters on the same inputs yields the same result_hash; a scenario never writes proposals or terms until promoted; a scenario whose inputs moved is refused at promotion as `scenario_stale` (it is not a stored status); a week that already has an approved or exported proposal refuses promotion (`proposal_conflict`); promoting is idempotent per scenario (`scenario_already_promoted`).

## Approval record

- Fields: proposal_id, proposal_version, decision, decided_by, mfa_auth_time, decided_at.
- Rule: an approval only counts while the proposal version equals the approved version.

## Export event

- Audit entry only: actor, proposal or scenario id, format, optional supplier, outcome (allowed or refused with reason). No file content is stored.

## Audit entries added or asserted

`proposal.refused` (code `auth_forbidden_role` for a viewer's export, `proposal_line_conflict` for a stale line save), `scenario.refused` (viewer's export), existing `proposal.superseded`, `proposal.submitted`, `proposal.approved`, `proposal.rejected`, `scenario.promoted`.
