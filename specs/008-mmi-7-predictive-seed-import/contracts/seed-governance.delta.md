# Contract delta: seed governance (MMI-7)

Additive changes on top of feature 002 contracts (`specs/002-mmi-operational-console/contracts/`). Schemas change first in `packages/contracts`; generated types follow. To be agreed with Agent 00 (T049).

## Gateway routes (`/forecast/imports`)

| Route | Change |
|---|---|
| `GET /template` | `sku` is the product column; `variant_id` is no longer in the template |
| `POST /{id}/validate` | rows resolved by SKU; quarantined rows for `import_unknown_sku` and `import_ambiguous_sku` carry the SKU in `params` (no new top-level field) |
| `POST /{id}/activate` | requires fresh MFA; body adds optional `reason_code` and `reason_detail` (a `reason_code` from the self-activation list is required for owner/admin self-activation); 403 `import_self_approval`; 409 `import_conflict` |
| `POST /rollback` | requires fresh MFA; body adds a required `reason_code` from the rollback list (`import_reason_required` when missing, `import_reason_invalid` when unknown, 422) and an optional `reason_detail` of at most 100 characters; 409 `import_conflict`, also for two rollbacks at the same moment |

## Schemas

- `seed_dataset.v1`: add optional `validated_by`, `mapping_chosen_by`, `rollback_reason_code`, `rollback_reason_detail`, `self_activation_reason_code`, `self_activation_reason_detail` (codes: rollback `wrong_figures`, `wrong_file`, `test`, `replaced_by_newer`, `other`; self-activation `only_person`, `urgent`, `other`; the detail is at most 100 characters, returned to admins only and never written to the audit trail); keep `approved` in the `status` enum as deprecated and never set (removal would be a breaking change; revisit in a later major version).
- `seed_validation_result.v1`: quarantine items add `sku`.
- `seed_mapping.v1`: canonical field `sku` required; `variant_id` stays an accepted mapping field for compatibility, but a row that supplies only `variant_id` is rejected with `import_sku_required`. The change is additive.
- Inventory series payload used by the importer: add optional `sku` per item if missing (T002).

## New error keys

| Key | Status | Meaning |
|---|---|---|
| import_sku_required | 422 (row) | The row has no SKU (a variant id was supplied instead) |
| import_self_approval | 403 | The uploader or validator cannot activate this dataset |
| import_conflict | 409 | Another activation or rollback ran at the same time |
| import_reason_required | 422 | A reason (a choice from the list) is required |
| import_reason_invalid | 422 | The reason is not in the list, or its detail is too long |
| import_erp_export_refused | 415 | The file looks like an ERP export, not a seed file |

All keys need Spanish text in the web and service locale files (T009).
