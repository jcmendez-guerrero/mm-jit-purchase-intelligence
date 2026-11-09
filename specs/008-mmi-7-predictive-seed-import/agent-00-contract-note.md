# Note for Agent 00: shared-contract changes from MMI-7 (draft for T049)

> Draft. Not sent: Agent 00 coordinates shared contracts, and posting this is your call. Reply expected from Agent 00: "confirmed" or the changes they want. When you have the answer, record it in `research.md` and tick T049.

## What this feature changes in shared places

All changes are additive. The full text is in `specs/008-mmi-7-predictive-seed-import/contracts/seed-governance.delta.md`.

| Where | Change |
|---|---|
| Inventory service `GET /export/series` | each item gains an optional `sku` (null when unknown). The forecast service uses it to match seed rows by SKU. |
| `packages/contracts/dto/seed_dataset.v1.schema.json` | new optional fields `validated_by`, `mapping_chosen_by`, `rollback_reason_code`, `rollback_reason_detail`, `self_activation_reason_code`, `self_activation_reason_detail`. `approved` stays in the status enum as deprecated and never set. |
| `packages/contracts/dto/seed_dataset_summary.v1.schema.json` | new schema for the `GET /imports` list item. |
| `packages/contracts/errors/error_codes.json` and `specs/002-mmi-operational-console/contracts/error-keys.md` | eight new keys: `import_sku_required`, `import_unknown_sku`, `import_ambiguous_sku`, `import_erp_export_refused`, `import_self_approval`, `import_conflict`, `import_reason_required`, `import_reason_invalid` (and the Spanish text in `apps/web/src/i18n/es-ES.json`). |
| Gateway `POST /api/imports/{id}/activate` and `POST /api/imports/rollback` | bodies take `reason_code` and `reason_detail` (rollback requires `reason_code`); both routes now need fresh MFA. |
| `packages/contracts/baseline/` and the generated Python and TypeScript types | regenerated. |

## What to confirm

1. The optional `sku` on the inventory series export is acceptable for the other agents that read that export.
2. No other agent is changing `error_codes.json`, `error-keys.md` or `es-ES.json` in a way that clashes (these shared files are the likely merge conflicts; the new keys are appended at the end).
3. Nobody depends on the removed free-text fields: `rollback_reason` and `self_activated_reason` were never released.
4. The migration order: forecast-service migration `0005_seed_governance` follows `0004`. Tell us if another agent also adds a forecast-service migration.

## Not changed

No Siweb request is added or changed. Procurement and the cost writer are untouched.
