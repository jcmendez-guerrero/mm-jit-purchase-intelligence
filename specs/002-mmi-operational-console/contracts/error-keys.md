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
| proposal_conflict | 409 | This week already has an approved proposal |
| unknown_role | 422 | A role is not valid |
| invalid_cost | 422 | A cost value is not valid |
| invalid_user_id | 422 | A user id is not valid |
| invalid_terms | 422 | Supplier order terms are not valid |
| revision_required | 428 | The caller must say which version it edited (If-Match) |
| terms_invalid_value | 422 | A terms value is out of range or malformed |
