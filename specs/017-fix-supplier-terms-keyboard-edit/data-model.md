# Data Model: Fix Supplier Terms Keyboard Edit

No persistent data changes. The feature touches screen state only.

## Terms form (screen state, existing)

- Every input is kept as text (`TermsForm` in `termsModel.ts`); the save payload parses it (`toPayload`). Lead time is text such as `"3"` and is sent as an integer or null.
- `form` is the value being edited; `baseline` is the last loaded value; the form is "dirty" when they differ.
- `view` holds the loaded terms and their version; it is `null` until the terms arrive, and the fields are locked while it is `null`.

### Invariants this fix must hold

1. The value sent on save equals the value shown in the field at that moment (FR-001, FR-002).
2. A load that finishes after the person started editing never replaces what they typed; the fields are locked until the first load completes (FR-003).
3. Save is based on the version that was loaded; a newer version is reported as a conflict (existing behaviour, unchanged).

## Saved terms version (existing, unchanged)

Numbered versions with a change reason. No new fields, states or transitions.
