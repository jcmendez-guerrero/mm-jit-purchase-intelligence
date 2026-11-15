# Implementation Plan: Data Quality and Forecast Intelligence (Agent 02)

**Branch**: `claude/speckit-mmi-4-spec-2232c0` | **Date**: 2026-11-13 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/012-data-quality-forecast-intelligence/spec.md`

## Summary

Make history quality, demand class, model choice, uncertainty and backtest accuracy visible and versioned per forecast. The audit (research.md R1) shows most building blocks already exist: ABC/XYZ/Syntetos-Boylan classification and eligibility reasons, stockout censoring, quality metrics and a review list in `inventory-service`; versioned forecast runs, an input hash, a backtest runner and an accuracy evaluator in `forecast-service`; a `quality` screen in the web app. The plan therefore **extends** them: it adds the missing pieces (per-product quality snapshot with coverage/gap days and anomaly flags with buyer decisions, a forecast explanation record that ties model, dataset and configuration versions to class/method/confidence, a per-product range and confidence label, per-product backtest vs. baseline, a portfolio view) and closes provenance gaps (nothing but ERP movements labelled observed). No new service, no always-on compute; heavy work stays in the existing scale-to-zero worker jobs.

## Technical Context

**Language/Version**: Python 3.12 (services), TypeScript/React (apps/web)

**Primary Dependencies**: FastAPI, SQLAlchemy Core, Alembic, Pydantic generated from `packages/contracts`, existing worker/outbox helpers in `mmi_common`; React with the existing es-ES i18n catalogue

**Storage**: PostgreSQL, one schema per service. Quality, class and anomaly data in `inventory-service`; explanation, range, backtest per product in `forecast-service`; no cross-schema SQL

**Testing**: pytest (unit, API contract, PostgreSQL integration, security-abuse), Playwright E2E for the Spanish UI; synthetic fixtures from `packages/testing` only

**Target Platform**: Azure Container Apps (scale to zero) behind the BFF; local dev with the same stack

**Project Type**: Multi-service web application (inventory-service, forecast-service, api-bff, apps/web)

**Performance Goals**: Portfolio view of 5,000 products under 3 s (precomputed aggregates, as the dashboard already does); full-catalogue backtest in the background under 15 min (SC-006)

**Constraints**: Shared EUR 120/month; decimals for money; UTC plus original timestamp text; free-text notes never stored; SKU-only user surface; additive contract changes only, negotiated with Agent 00

**Scale/Scope**: About 5,000 variants, up to a few years of daily history; 3 read screens, 1 backtest action, 1 anomaly decision action

## Constitution Check

*GATE: passed before Phase 0; re-checked after Phase 1.*

| Principle | Result |
|-----------|--------|
| I. Least-privilege integrations | Pass. Feature is read-only against Siweb; no new write, no new host or method. |
| II. Privacy and synthetic data | Pass. Fixtures synthetic; anomaly decisions store actor id and enumerated reason code only; no notes, no tax ids. |
| III. Explainable, human-controlled | Pass. Strengthens it: every forecast carries versions, class, method, range, confidence. Auto-suggestion is withheld for low confidence; humans still approve. |
| IV. Contract-first | Pass with action: new fields/endpoints are added to JSON Schemas and the contract matrix first, additively, via Agent 00. |
| V. Testable, observable, cost-bounded | Pass. Tests listed below; compute runs in existing worker jobs; no new always-on resource. |

No violations; Complexity Tracking is empty.

## Project Structure

### Documentation (this feature)

```text
specs/012-data-quality-forecast-intelligence/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── quality-intelligence.md
├── checklists/requirements.md
└── tasks.md              # created by /speckit-tasks
```

### Source Code (repository root)

```text
packages/contracts/                      # schemas first: explanation, quality snapshot, anomaly, backtest result; matrix entry
services/inventory-service/
├── src/quality/                         # extend: coverage/gaps, anomaly rules, snapshot builder, excluded movement counts
├── src/classification/                  # reuse segments.py; thresholds read from the business policy configuration
├── src/api/                             # quality + anomaly decision + portfolio endpoints
├── migrations/versions/0008+            # data_quality_snapshot, anomaly_flags
└── tests/
services/forecast-service/
├── src/runs/                            # explanation + range/confidence at run time; versions recorded
├── src/backtest/                        # per-product backtest vs. baseline, stored as own versioned results
├── src/db/tables.py + migrations/       # forecast_explanations, product_backtest
└── tests/
services/api-bff/src/routes/             # thin orchestration and RBAC only (no business rules)
apps/web/src/features/quality/           # extend: quality summary, explanation panel, backtest view, portfolio
apps/web/src/i18n/es-ES.json             # all new user strings
apps/web/tests/e2e/                               # Playwright, Spanish UI
```

**Structure Decision**: Extend the existing services and screens; no new service. Business rules stay in the owning services, the BFF only orchestrates and enforces roles (guardrail from the brief).

## Clarified decisions reflected in this plan

- Excluding or re-including an anomalous day needs a recent second-factor check, enforced at the BFF; accepting needs none.
- Not-eligible, manual-review-only and low-confidence products show the conservative min/max labelled "not a forecast".
- Stockout days are left out of what the forecast learns from; no demand is estimated for them.
- One full-catalogue backtest runs at a time; identical inputs reuse the result.
- Explanations, quality snapshots, anomaly decisions and backtest results are kept 5 years in full detail.
- Portfolio data flow: forecast-service publishes eligibility and confidence per variant on `forecast.completed`; inventory-service builds the portfolio from it (products without a value count as "pending"), so no cross-service query is needed.
- Thresholds come from the business policy configuration already on main (feature 002 console), with the current defaults as fallback; T010 confirms which thresholds it stores.
- Playwright specs live in `apps/web/tests/e2e/`.

## Phase summary

- **Phase 0** (research.md): audit of existing capability with file evidence, and decisions on anomaly rules, confidence derivation, censored-day treatment, baseline, and where each record lives.
- **Phase 1** (data-model.md, contracts/, quickstart.md): entities, additive API contract, runnable validation scenarios.
- **Phase 2** (tasks.md): produced by `/speckit-tasks`; tests before implementation within each story.
