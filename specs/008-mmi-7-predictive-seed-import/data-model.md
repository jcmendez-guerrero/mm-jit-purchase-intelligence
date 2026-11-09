# Data Model: Predictive Seed Import and Dataset Governance (MMI-7)

Owner: forecast service schema. Existing tables from feature 002 migration 0003 are reused; this feature adds columns in one new migration (T007).

## Entities

| Entity | Table | Key fields | Change in this feature |
|---|---|---|---|
| Seed Dataset | `seed_datasets` | id, version, name, status, origin, file_sha256, file_ref, uploader, uploaded_at, activated_by, activated_at, supersedes_id, accepted_count, quarantined_count, kind_summary | add `validated_by`, `mapping_chosen_by`, `rollback_reason_code`, `rollback_reason_detail`, `self_activation_reason_code`, `self_activation_reason_detail` (code from a fixed list; detail at most 100 characters, admins only) |
| Seed Row | `seed_rows` | dataset_id, variant_id, day, quantity, kind, provenance, warehouse | add `sku` (as supplied, kept for display; users never see variant_id) and `day_text` (the date exactly as written in the file; `day` is the normalised calendar day) |
| Quarantine Entry | `seed_quarantine` | dataset_id, row_number, reason key | none; the SKU travels in `reason_params` (no raw row is stored) |
| Column Mapping | `seed_mappings` | id, name, column map | none |
| Import Job | `import_jobs` | id, dataset_id, stage, state, queued_at, started_at, requested_by, error | none |
| Activation Record | audit log | actor, action, dataset id, version, UTC time | new action `seed.self_activated`; the audit entries of a rollback and of a self-activation hold the reason code, never the detail |

## States and transitions

`uploaded` → `validated` → `active` → `superseded` or `rolled_back`; `uploaded`/`validated` → `rejected`. The earlier `approved` state is never set (kept in the schema enum as deprecated); activation is the approval.

- Activation: allowed only from `validated`, with accepted rows, no mixed origin, duplicate-file acknowledgement if the checksum repeats, an approver who is not the uploader or the validator (or an audited owner/admin self-activation with a written reason), and fresh MFA. The previous active dataset becomes `superseded`.
- Rollback: allowed only from `active`, with a reason and fresh MFA. The dataset becomes `rolled_back` and the one it superseded (if any) becomes `active` again. No rows are deleted.
- Concurrency: the existing unique index on `status = 'active'` already allows one active dataset; a losing activation or rollback maps the integrity error to `import_conflict`.

## Validation rules

- Rows resolve by SKU to a variant through the inventory series source; unresolved or ambiguous SKU, duplicate (sku, day, kind), bad quantity or date go to quarantine with a Spanish reason key. A `variant_id`-only file is rejected per row (`import_sku_required`).
- Every row has one provenance (observed, estimated, manual); a missing one is estimated. A dataset cannot mix origins.
- Notes, tax ids and personal data are discarded at load. Files recognised as ERP exports are refused.
- Actual ERP demand prevails on days it covers; seeds rescue only variants whose sole ineligibility is "new".
