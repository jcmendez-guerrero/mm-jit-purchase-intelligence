# Threat model template

This file is a **method**, not a record. Fill in a copy in the internal wiki; findings and the current security posture must not be committed to this public repository.

## 1. Scope

- System or change being modelled, trust boundaries, actors (viewer, buyer, approver, admin, services, external systems)

## 2. Data flow

- Diagram: sources, processes, stores, flows, boundaries
- Data classes per flow (see `data-classification.md`)

## 3. Threats (STRIDE per element)

| ID | Element | Category (S/T/R/I/D/E) | Threat | Existing control | Residual risk | Action / owner |
|----|---------|------------------------|--------|------------------|---------------|----------------|

## 4. Required focus areas for MMI

- Shared full-scope ERP token: writer service residual risk, egress limits, audit and alerting for unmatched writes
- Allowlist bypass (method, path, host, redirect)
- Forged, replayed or poisoned queue messages
- Approval abuse: self-approval, stale MFA, edit after approval
- Prompt injection through product names or notes (data, never instructions)
- Shared rate-limit exhaustion affecting the other application
- Public-repository leakage

## 5. Review

- Date, reviewers, next review trigger (new integration, new data class, incident)
