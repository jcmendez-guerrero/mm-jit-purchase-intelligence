# Note for Agent 00: shared-contract changes from MMI-5 (draft for T003)

> Draft. Not sent: Agent 00 coordinates shared contracts, and posting this is your call. Reply expected from Agent 00: "confirmed" or the changes they want. When you have the answer, record it in `research.md`.

All changes are additive or tighten a role gate. The full text is in `contracts/proposals-scenarios.delta.md`.

| Where | Change |
|---|---|
| `packages/contracts/errors/error_codes.json`, `specs/002-mmi-operational-console/contracts/error-keys.md`, `apps/web/src/i18n/es-ES.json` | two new keys: `proposal_line_conflict` (409) and `proposal_superseded` (409), with Spanish text. `version_conflict` is unchanged for every other use. |
| Gateway `GET /api/proposals/{id}/export` and `GET /api/scenarios/{id}/export` | role gate is buyer, approver or admin (a viewer gets 403 `auth_forbidden_role`). |
| Procurement service `GET /scenarios/{sid}/export` and `GET /proposals/{id}/export` | the same gate; a refused request leaves a `proposal.refused` or `scenario.refused` audit entry. The proposal route no longer needs the buyer role specifically, so approvers and admins can export. |
| Procurement service `GET /proposals` and `GET /proposals/{id}` | `status` may now be `superseded` (it already could be at the data level); the detail response gains `review_notes` (variants needed but with no eligible supplier) (excess over the budget cap, decimal string). |

## What to confirm

1. No other agent's consumer calls the two export routes as a viewer (the dashboard agent does not).
2. The two new error keys and the `review_notes` field are acceptable additions.
3. Open item (not changed here): supplier terms already hold discount tiers; nothing is missing, so no request to the supplier-management owner.
