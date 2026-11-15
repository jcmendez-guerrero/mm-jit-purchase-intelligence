# Contract delta: Procurement Proposals & Scenarios (draft for Agent 00)

> Draft, not sent. Agent 00 coordinates shared contracts; posting this is the owner's call.

All changes are additive or tighten a role gate. No schema in `packages/contracts` changes shape.

| Where | Change |
|---|---|
| Gateway `GET /api/proposals/{id}/export` | role gate becomes buyer, approver or admin (was viewer, buyer, approver, admin). A viewer gets 403 `auth_forbidden_role` and an audit entry. |
| Gateway `GET /api/scenarios/{id}/export` | same role gate and audit entry. |
| Procurement service `GET /scenarios/{sid}/export` | requires buyer, approver or admin (was any signed-in role). The proposal export gate in the service (`require("buyer")`) is widened the same way if the role check does not already admit approver and admin. |
| Error keys | `proposal_line_conflict` (HTTP 409, Spanish "La línea ha cambiado, recarga para continuar") is returned for a stale proposal-line save; the existing `version_conflict` stays unchanged for every other use; `proposal_superseded` (HTTP 409) for submit, approve or export on a superseded proposal. Added to `packages/contracts/errors/error_codes.json`, `specs/002-mmi-operational-console/contracts/error-keys.md` and `apps/web/src/i18n/es-ES.json`. |
| Proposal detail | `GET /proposals/{id}` gains `review_notes` (needed variants with no eligible supplier) and `over_budget` (the excess over the cap as a decimal string, "0" when within it). |
| Responses | `GET /proposals` and `GET /proposals/{id}` already return `status`; `superseded` is documented as a possible value. |

## To confirm with Agent 00

1. Tightening the export role gate does not break another agent's consumer (the dashboard agent does not call these routes).
2. The two new error keys are acceptable as additions.
