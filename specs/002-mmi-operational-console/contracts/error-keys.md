# Stable error keys (examples; full catalogue built in Phase 1)

Keys are English identifiers; messages are Spanish in `apps/web` and service locale catalogues. A test fails if a key lacks an es-ES message.

| Key | HTTP | Meaning |
|---|---|---|
| auth.forbidden_role | 403 | Role does not allow the action (refusal recorded) |
| auth.mfa_stale | 403 | Second factor older than 5 minutes |
| approval.self_not_allowed | 403 | Creator/last editor cannot approve |
| approval.fewer_than_two_approvers | 409 | Submission needs two eligible users |
| revision.conflict | 412 | Stale If-Match; body returns current version |
| terms.negative_amount | 422 | Negative money or quantity |
| terms.threshold_below_minimum | 422 | Free-shipping threshold below minimum order |
| terms.window_overlap | 422 | Overlapping validity windows |
| terms.invalid_weekday | 422 | Weekday outside 1..7 or duplicated |
| policy.out_of_range | 422 | Service level outside 0–100 or max below min |
| import.file_too_large | 413 | Size cap exceeded |
| import.type_not_allowed | 415 | Extension/signature mismatch, macros, or unsupported type |
| import.unknown_variant | 422 (row) | Variant not found |
| import.negative_quantity | 422 (row) | Quantity below zero |
| import.date_out_of_range | 422 (row) | Date outside allowed range |
| import.duplicate_row | 422 (row) | Repeated variant/day/kind |
| import.mixed_origin | 409 | Synthetic and real data in one dataset |
| import.duplicate_file | 409 | Same checksum already uploaded; explicit decision needed |
| scenario.infeasible | 200 | Result explains shortfall causes |
