# Research: Fix Supplier Terms Keyboard Edit

Root cause is **not yet established**: dependencies are not installed in this worktree, so the check could not be run during planning. This file records what the code shows and the ordered hypotheses to test first.

## What the code already does

- `SupplierTermsEditor` locks every field until the saved terms arrive (`readOnly = !canEdit || view === null`) and its loader deliberately does not depend on `t`, so neither a late response nor a translation reload should erase typing. This answers spec story 2 for the screen as it stands; verify rather than rebuild.
- `FormField` is a plain controlled input (`value` + `onChange`), with nothing key-specific.
- The test already waits for `toHaveValue("3")` before typing, citing an earlier intermittent failure.
- `SuppliersScreen` mounts `SupplierTermsEditor` and `OverrideEditor` together; both have a lead-time field (`f-lead`, `o-lead`).
- Save sends `toPayload(form)`, where `lead_time_days` is `intOrNull(form.lead_time_days)`.

## Decision 1: Reproduce before changing anything

- **Decision**: Run the check un-quarantined locally, with a trace, and capture the focused element and the field value after each key press.
- **Rationale**: The Jira text gives two candidates (editor input handling, or the test's tab order) and the code review above does not settle it.
- **Alternatives considered**: Fixing by guess (for example another wait) — rejected; that is how the current intermittent workaround appeared.

## Decision 2: Hypotheses, in the order to test

| # | Hypothesis | How to confirm | Fix site |
|---|------------|----------------|----------|
| H1 | Focus lands on another input with the same label text (the `OverrideEditor` lead time), so `7` is typed there and the terms form keeps `3` | Log `document.activeElement.id` after `tabTo`; expect `f-lead` | Test (scope the lookup to the terms form) |
| H2 | The terms form is re-initialised after typing (a second `load()` or a remount via the list refresh), restoring `3` | Log form value before save; watch network calls to `/api/suppliers` and `/terms` | Screen |
| H3 | `ControlOrMeta+a` selects the page rather than the field text, so typing `7` appends or is lost | Check the input value after the key presses | Test |
| H4 | Enter on the save button submits while a stale `form` closure is in use | Compare the request body with the visible field value | Screen |

- **Rationale**: H1 matches "the test's tab order" in the Jira text and the two lead-time fields on one screen; H2 matches "input handling in the supplier terms editor".
- **Output required by FR-004**: the confirmed hypothesis, with the evidence, is written to the section at the end of this file.

## Decision 3: Test design after the fix

- **Decision**: Remove `test.fixme`; keep the load wait (or replace it with a check that the fields are enabled); scope field lookups to the terms form; add a second keyboard case that edits a money term (minimum order value) and asserts the saved string.
- **Rationale**: FR-005 and FR-006; avoids matching the same label in `OverrideEditor`.
- **Alternatives considered**: Loosening the assertion — rejected; the assertion is the requirement.

## Decision 4: Stability proof

- **Decision**: Run the check at least 20 consecutive times (`--repeat-each=20`) and record the result in the PR.
- **Rationale**: SC-001; the earlier failure was intermittent.

## Root cause (to be completed)

_Not yet known. Fill in during implementation: which hypothesis held, the evidence, and whether the fix is in the screen or in the check._
