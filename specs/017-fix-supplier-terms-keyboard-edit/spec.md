# Feature Specification: Fix Supplier Terms Keyboard Edit (e2e gate)

**Feature Branch**: `claude/jira-spec-mmi-12-c32d10`

**Created**: 2026-11-16

**Status**: Draft

**Input**: User description: "implement jira spec on MMI-12" — Jira [MMI-12](https://mundomascotix.atlassian.net/browse/MMI-12) ("Fix failing e2e test: supplier terms keyboard edit saves lead time 3 instead of 7", type Error, epic MMI-1). Numbers 014 to 016 are taken by open pull requests (27, 30 and 29), so this one is **017** (renumbered from 014 on the request of Agent 00 in its review of PR 31).

## Context

A buyer maintains each supplier's commercial terms (lead time, minimum order, delivery charge, discounts and so on) on the supplier terms screen (feature 007). Changes are saved as a new version with a reason. The automated accessibility run includes a "reference task" that does this **using only the keyboard**: open a supplier, go to the lead-time field, replace `3` with `7`, enter a reason and save with Enter.

That check currently fails: the saved lead time is `3` (the original value), not `7`. It fails on `main` too, so it is not caused by the MMI-5 branch (spec 011). To unblock that branch the check was **quarantined** (skipped), which means the end-to-end quality gate no longer proves that a keyboard-only user can edit and save a supplier term.

This is a bug-fix feature. Either a real defect makes a keyboard edit of a supplier term lose the typed value (a buyer who types `7` silently saves `3`), or the check itself is wrong. The first thing to establish is which. It adds no business capability, no ERP request and no change to purchasing rules; Siweb360 stays the system of record.

Out of scope: new supplier-terms fields or rules; changes to how terms are versioned, reviewed or written to the ERP; redesign of the supplier screen; fixing other quarantined or failing checks.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A keyboard-typed supplier term is the value that gets saved (Priority: P1)

A buyer who uses only the keyboard (or assistive technology) opens a supplier, moves to a term field such as "Plazo de entrega (días)", replaces the value, fills the change reason and saves. The saved version must contain exactly what they typed.

**Why this priority**: Saving a different value from the one typed is a silent data error in commercial terms that feed purchase proposals. It also blocks keyboard-only users from a core task.

**Independent Test**: Open a supplier whose lead time is 3, replace it with 7 by keyboard, add a reason, save with Enter; the saved version has lead time 7.

**Acceptance Scenarios**:

1. **Given** a supplier with lead time 3 is open and its saved terms have finished loading, **When** the buyer selects the field's content, types `7`, enters a reason and saves with Enter, **Then** the new version is saved with lead time 7 and every other term unchanged.
2. **Given** the same supplier, **When** the buyer makes the same edit with the mouse, **Then** the saved result is identical to the keyboard edit.
3. **Given** the buyer edits a different term (for example the minimum order value) by keyboard, **When** they save, **Then** that value is saved as typed, so the fix is not specific to the lead-time field.

---

### User Story 2 - Typed input is never overwritten by late-arriving data (Priority: P2)

If the saved terms arrive after the buyer has started typing, the buyer's input must not be silently replaced by the loaded values, and they must not be able to save a version based on terms they have not seen.

**Why this priority**: The test already waits for the terms to load because typing earlier was overwritten ("an intermittent failure"). A real user on a slow connection can hit the same race.

**Independent Test**: Delay the terms response, start typing before it arrives, and observe that the screen either blocks editing until loading finishes or keeps what was typed.

**Acceptance Scenarios**:

1. **Given** the saved terms are still loading, **When** the buyer tries to edit a term field, **Then** the fields are not editable (or the typed value is preserved), and the saved result never silently differs from what is shown on screen.
2. **Given** the terms finished loading, **When** the buyer edits and saves, **Then** the saved version is based on the loaded version and any conflict is shown, not overwritten.

---

### User Story 3 - The end-to-end gate proves keyboard editing again (Priority: P3)

The quarantined keyboard check runs again, passes, and is part of the end-to-end gate, so a future regression of keyboard editing fails the gate.

**Why this priority**: Closing the bug is only durable if the check that found it is active. It also removes the standing exception that makes the gate fail for every branch.

**Independent Test**: Run the end-to-end gate on a clean branch and confirm the keyboard check executes, passes and no check is skipped for this reason.

**Acceptance Scenarios**:

1. **Given** the fix is in place, **When** the end-to-end gate runs, **Then** the keyboard supplier-term check runs (not skipped) and passes.
2. **Given** the same check is run repeatedly (at least 20 consecutive runs), **When** results are compared, **Then** it passes every time, with no intermittent failure.
3. **Given** any branch, **When** the gate runs, **Then** it no longer reports `fail` because of this check.

---

### Edge Cases

- The buyer replaces the value with a number of more than one digit, or clears the field and types a value.
- The buyer tabs through the field without typing: the value must stay as loaded (no accidental change to 3 or to empty).
- The buyer types an invalid lead time (negative, text, decimal): the existing validation message appears and nothing is saved.
- The supplier is changed by someone else between load and save: the conflict is reported as it is today.
- Reduced-privilege roles (viewer) still see the terms read-only.
- If investigation shows the defect is in the check (for example its tab order) and not in the screen, the check is corrected to match real keyboard behaviour, and the finding is recorded.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST save, for every supplier term field, exactly the value the buyer typed, whether entered by keyboard or by mouse.
- **FR-002**: The system MUST NOT replace a value the buyer has typed with a previously loaded or default value (such as the original lead time) when the buyer saves.
- **FR-003**: While a supplier's saved terms are loading, the system MUST either prevent editing or preserve what was typed, and MUST NOT let the buyer save terms they have not seen.
- **FR-004**: The root cause MUST be identified and recorded in the feature's notes, stating whether it was a defect in the screen or in the check.
- **FR-005**: The quarantine marker on the "reference task 3 by keyboard: edit one supplier term and save it" check MUST be removed, and the check MUST run and pass in the end-to-end gate.
- **FR-006**: A regression check MUST cover keyboard editing of at least one numeric term and one money term, so the fix is not limited to the lead-time field.
- **FR-007**: The fix MUST NOT change term versioning, validation rules, the reason requirement, role permissions, audit entries or any ERP request.
- **FR-008**: All user-visible text stays Spanish (es-ES); no new user-facing wording is required unless a loading or conflict message is added, in which case it is localized.
- **FR-009**: Tests MUST use synthetic fixtures only; no real supplier, price or export data.

### Key Entities

- **Supplier terms**: The commercial conditions of one supplier (lead time, minimum order, delivery charge, discounts, payment terms, validity). Saved as numbered versions with a change reason.
- **Terms editor form**: The screen state holding the values the buyer is editing before they are saved as a new version.
- **Keyboard reference task**: The automated end-to-end check that edits one supplier term using only the keyboard and verifies the saved value.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A keyboard-only edit of a supplier term saves the typed value in 100% of runs (at least 20 consecutive runs of the reference task with no failure).
- **SC-002**: The end-to-end gate reports no failure attributable to this check and no check is skipped for this reason (zero quarantined checks tied to MMI-12).
- **SC-003**: A buyer can edit and save one supplier term by keyboard alone in under 1 minute, with the saved value equal to what they typed.
- **SC-004**: For the tested term fields (lead time, minimum order value), mouse and keyboard edits produce identical saved results.
- **SC-005**: No change to the number of fields, validation messages, permissions or audit entries on the supplier terms screen, other than any loading-state message.

## Assumptions

- The defect reproduces on `main` and is in either the supplier terms editor (feature 007) or the check; the investigation decides which, and the fix goes where the cause is.
- The existing wait for saved terms to load in the check stays or is replaced by a screen-level guarantee; either way the check must not depend on timing luck.
- Roles other than buyer keep their current access to the terms screen; only the buyer role is exercised by the reference task.
- The "e2e gate" is the existing end-to-end quality gate run in CI and by `python -m gates run`; its definition is unchanged.
- The Jira issue is a bug under epic MMI-1; no new epic or ticket is created by this spec.
