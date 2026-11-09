# Stable error keys (examples; full catalogue built in Phase 1)

Codes are snake_case identifiers (the repo convention enforced by `mmi_common.errors`); services return codes only, never sentences. The machine-readable source is `packages/contracts/errors/error_codes.json`; Spanish messages live in `apps/web/src/i18n/es-ES.json` under `errors.<code>`, and a test fails if a code lacks one or if this table and the JSON drift apart.

| Key | HTTP | Meaning |
|---|---|---|
| auth_forbidden_role | 403 | Role does not allow the action (refusal recorded) |
| auth_mfa_stale | 403 | Second factor older than 5 minutes |
| approval_fewer_than_two_approvers | 409 | Submission needs two eligible users |
| revision_conflict | 412 | Stale If-Match; body returns current version |
| terms_negative_amount | 422 | Negative money or quantity |
| terms_threshold_below_minimum | 422 | Free-shipping threshold below minimum order |
| terms_window_overlap | 422 | Overlapping validity windows |
| terms_invalid_weekday | 422 | Weekday outside 1..7 or duplicated |
| policy_out_of_range | 422 | Service level outside 0–100 or max below min |
| import_file_too_large | 413 | Size cap exceeded |
| import_type_not_allowed | 415 | Extension/signature mismatch, macros, or unsupported type |
| import_unknown_variant | 422 (row) | Variant not found |
| import_negative_quantity | 422 (row) | Quantity below zero |
| import_date_out_of_range | 422 (row) | Date outside allowed range |
| import_duplicate_row | 422 (row) | Repeated variant/day/kind |
| import_mixed_origin | 409 | Synthetic and real data in one dataset |
| import_duplicate_file | 409 | Same checksum already uploaded; explicit decision needed |
| scenario_infeasible | 200 | Result explains shortfall causes |
| margin_below_minimum | 409 | Margin after the update would be below 15%; release blocked unless an admin overrides |
| margin_pvp_unavailable | 409 | Selling price missing or stale; margin check unavailable |
| margin_above_maximum | 200 (flag) | Margin above its maximum; informational |
| cost_no_entries_in_stock | 409 | No lot entry with remaining stock; no update request is created |
| override_admin_required | 403 | Only an admin may replace the median |
| override_reason_required | 422 | An override needs a reason |
| policy_override_requires_approval | 202 | Override saved as pending; the recommendation stays in force |
| policy_override_self_approval | 403 | The requester cannot approve their own override |
| stocking_floor_required | 422 | An always-stocked product needs a floor of at least 1 |
| cost_lot_lookup_unavailable | 503 | Inventory could not be reached; the cost-update request fails visibly and is retried |
| import_invalid_quantity | 422 (row) | Quantity is not a number |
| import_invalid_date | 422 (row) | Date is not a valid calendar date |
| import_missing_provenance | 422 (row) | The provenance label is empty |
| override_release_by_setter | 403 | The admin who set an override cannot release it |
| roles_invalid | 422 | A role is not valid |
| roles_last_admin | 409 | The last administrator cannot be removed |
| role_mirror_failed | 503 | A role change could not be mirrored to the purchasing side; it is retried |
| auth_unauthenticated | 401 | Sign-in is required |
| auth_csrf_invalid | 403 | The CSRF token is missing or invalid |
| downstream_refused | 400 | A downstream service refused the request |
| downstream_unavailable | 502 | A downstream service is unavailable |
| authentication_unavailable | 503 | Service identity could not be obtained |
| request_invalid | 422 | The request body or parameters are not valid |
| separation_of_duties | 403 | The creator or last editor cannot approve |
| no_eligible_approver | 409 | Submission needs another eligible approver |
| not_an_approver | 403 | Only users with the approver role can decide |
| mfa_required | 403 | A recent second factor is required |
| version_conflict | 409 | The record changed since it was read |
| invalid_proposal_state | 409 | The proposal state does not allow this action |
| invalid_quantity | 422 | A quantity must be a whole number of zero or more |
| override_release_same_person | 403 | The admin who set an override cannot release it |
| median_required | 409 | The released value must be the lot median or the admin override |
| not_an_admin | 403 | Only an admin can set a cost override |
| negative_value | 422 | A value must not be negative |
| inventory_unavailable | 503 | Inventory could not be queried for the lots in stock |
| pvp_unavailable | 503 | The selling price (PVP) could not be queried |
| vat_unknown | 422 | The product VAT is unknown, so a net cost cannot be converted |
| negative_cost | 422 | A cost must not be negative |
| invalid_source | 422 | The cost source is not allowed |
| invalid_lot | 422 | The lot identifier is missing or too long |
| unknown_variant | 422 | The variant is not known |
| unknown_supplier | 422 | The supplier is not known |
| not_a_buyer | 403 | Only buyers can do this |
| unknown_parameter | 422 | The forecast parameter is not on the approved list |
| unknown_exclusion | 404 | The demand exclusion does not exist |
| policy_override_pending | 409 | A request for that field is already pending |
| policy_override_not_found | 404 | The override request does not exist |
| policy_override_not_pending | 409 | The override request is not in a state that allows this |
| margin_unavailable | 409 | There is no selling price, so the margin cannot be checked |
| import_decompression_limit | 413 | The workbook expands beyond the allowed size |
| import_too_many_rows | 413 | The file has more rows, columns or sheets than allowed |
| import_missing_column | 422 | A required column is missing or the file is empty |
| import_unknown_kind | 422 | The data type is not one of the allowed values |
| import_ambiguous_time | 422 | The local time is ambiguous because of the clock change |
| import_dataset_state | 409 | The dataset is not in a state that allows this |
| import_unknown_dataset | 404 | The dataset does not exist |
| import_failed | 500 | A background import failed unexpectedly |
| import_unknown_job | 404 | The import job does not exist |
| import_job_not_rerunnable | 409 | Only a failed import job can be re-run |
| import_nothing_to_activate | 409 | The dataset has no accepted rows |
| import_mapping_name_taken | 409 | A mapping with that name already exists |
| scenario_invalid | 422 | The scenario parameters are not valid |
| scenario_stale | 409 | The inputs changed since the scenario was computed |
| unknown_scenario | 404 | The scenario does not exist |
| scenario_not_ready | 409 | The scenario is not ready |
| scenario_already_promoted | 409 | The scenario was already turned into a proposal |
| idempotency_key_required | 422 | An Idempotency-Key header is required |
| proposal_conflict | 409 | This week already has an approved proposal |
| unknown_role | 422 | A role is not valid |
| invalid_cost | 422 | A cost value is not valid |
| invalid_user_id | 422 | A user id is not valid |
| invalid_terms | 422 | Supplier order terms are not valid |
| revision_required | 428 | The caller must say which version it edited (If-Match) |
| terms_invalid_value | 422 | A terms value is out of range or malformed |
| local_load_type_not_allowed | 415 | The file is not a plain CSV or XLSX |
| local_load_file_too_large | 413 | The file exceeds the size or decompression limit |
| local_load_too_many_rows | 413 | The file has more rows than allowed |
| local_load_macros_or_links | 415 | The workbook has macros, formulas or external links |
| local_load_signature_mismatch | 422 | The file columns do not match the expected export |
| local_load_interpretation_not_acknowledged | 409 | Tax and price interpretation was not confirmed |
| local_load_inventory_required | 409 | Movements need the inventory loaded first |
| local_load_unreachable | 502 | The local loader could not be reached |
| local_load_platform_unreachable | 502 | Data was parsed but the platform did not accept it |
| local_load_unknown_kind | 404 | The file kind is not supported |
| supplier_possible_duplicate | 409 | A supplier with a very similar name exists |
| supplier_invalid | 422 | A supplier field is missing or not valid |
| supplier_deactivated | 409 | The supplier is deactivated |
| supplier_merged | 409 | The supplier was merged into another |
| supplier_not_found | 404 | The supplier does not exist |
| supplier_version_conflict | 412 | The supplier was changed by someone else (If-Match) |
| link_sku_unknown | 422 | The SKU is not in the loaded catalogue |
| link_cost_invalid | 422 | The link cost is missing or not valid |
| link_currency_mismatch | 422 | The cost currency differs from the supplier currency |
| link_not_found | 404 | The product is not linked to the supplier |
| bulk_criteria_invalid | 422 | Bulk assignment needs SKUs or a search text |
| bulk_preview_stale | 409 | The bulk preview expired or was already applied |
| bulk_conflicts_unresolved | 409 | Products with another preferred supplier were not resolved |
| bulk_file_invalid | 422 | The bulk file needs SKU and supplier columns |
| merge_same_supplier | 422 | A supplier cannot be merged into itself |
| merge_currency_mismatch | 409 | Suppliers with different currencies cannot be merged |
| merge_open_lines | 409 | The supplier has lines in open proposals |
| review_item_not_found | 404 | The review item does not exist |
| review_item_closed | 409 | The review item was already resolved |
| payload_too_large | 413 | The request body is larger than a supplier, terms or link change may be |
| idempotency_key_reuse | 422 | The Idempotency-Key was already used with different content |
| invalid_idempotency_key | 422 | The Idempotency-Key is too long or has control characters |
| proposal_has_deactivated_supplier | 409 | A proposal line belongs to a deactivated supplier |
| fx_rate_missing | 422 | No stored exchange rate for the supplier currency |
| fx_rate_stale | 422 | The stored exchange rate is older than 7 days |
| import_sku_required | 422 | The row has no SKU (a variant id was supplied instead) |
| import_unknown_sku | 422 | The SKU is not in the synchronised catalogue |
| import_ambiguous_sku | 422 | The SKU matches more than one product |
| import_erp_export_refused | 415 | The file looks like an ERP export, which is local-only |
| import_self_approval | 403 | The uploader or validator cannot activate this dataset |
| import_conflict | 409 | Another activation or rollback ran at the same time |
| import_reason_required | 422 | A reason (a choice from the list) is required |
| import_reason_invalid | 422 | The reason is not in the list, or its detail is longer than 100 characters |
