# Agent and contributor rules

Mundo Mascotix Intelligence (MMI): inventory intelligence and weekly purchasing for a veterinary pharmacy and pet shop. Siweb360 is the ERP and system of record. This repository is **public**.

Authoritative documents: `.specify/memory/constitution.md` (v1.3.0), `specs/001-mmi-purchase-intelligence/` (spec, plan, tasks, contracts) and `docs/architecture/implementation-plan.md`.

## Non-negotiable rules

1. **Synthetic data only.** Never commit or use real exports, raw Siweb responses, real SKUs, products, suppliers, prices, quantities, names, e-mails, tenant/subscription/app IDs or resource names. Tests use fixtures from `packages/testing`.
2. **No secrets.** No tokens, keys, connection strings or real `.bicepparam`/`.tfvars` files. Commit `*.example` templates only. Secrets live in Azure Key Vault.
3. **Siweb is read-only except two writes (constitution v1.3.0).** The connector (`services/siweb-connector`) allows only the GET allowlist in `specs/.../contracts/siweb-allowlist.md`. The permitted writes are (a) `PUT /inventory/products/{id}/suppliers/{contact_id}` (supplier cost) and (b) the app-owned supplier-conditions block inside the supplier note (read-merge-write, one supplier per request, everything outside the block untouched). Both only from `services/siweb-cost-writer`, only after buyer/admin review with fresh MFA, always audited. Write (b) stays disabled until Gate 0 confirms its operation and it is verified on a non-production record. Anything else is refused before a request is built.
4. **Humans decide purchases.** No autonomous writes, no self-approval (approver is not the creator or last editor), no order sending to suppliers.
5. **Money is `Decimal`** (never float). Store UTC plus the original timestamp string. Key products by Siweb `variant_id`. Users always see and supply the SKU; Siweb ids are used only in API calls, resolved from the SKU via the synced catalogue. The one exception is data loaded locally from UI exports (feature 004), which has no `variant_id`: it uses SKU-derived surrogate ids from the reserved range starting at 9,000,000, never put in any Siweb request (the request is refused as pending link), and is never mixed with data collected from the real ERP.
6. **Never drop data silently.** Malformed or ambiguous records go to the quarantine/review list.
7. **Free-text notes are never stored, logged, displayed or used in decisions** (only a `has_note` flag). The one exception: the writer may hold a supplier note in memory during write (b) to preserve content outside the app's own block and to read that block for discrepancy detection. `supplier_cif` is discarded before storage.
7a. **Real exports stay local.** Real inventory, movements and supplier exports load only through the local-only loader (command, and screen upload in the local environment) from a gitignored private folder; the loader is absent/disabled in any cloud configuration. Committed fixtures and tests are synthetic only.
8. **UI is Spanish (es-ES) only**, with EUR and Spanish date/number formats; no hard-coded user-facing strings.
9. **Contract-first.** Change JSON Schemas in `packages/contracts` first; generated types follow. Each service owns its schema, role and migrations; no cross-schema SQL.
10. **Shared budget EUR 120/month.** Scale to zero, replica and job caps; reuse shared platform resources.

## Workflow

- Work from `specs/001-mmi-purchase-intelligence/tasks.md`; mark tasks `[X]` when done. Tests come before implementation within a story.
- Gate 0 items (research V1–V7) are open assumptions until verified; T135 (supplier-cost PUT semantics) must be verified on a non-production record before any write reaches the real ERP.
- Security posture and findings go to the internal wiki, not to this repo.
- PRs follow `.github/pull_request_template.md` (data, security, cost, contract impact).
- Shared interfaces are frozen and versioned in `docs/architecture/integration/contract-matrix.json`; change them through Agent 00 (see the README there) and run `python -m gates run` before the PR.
- The gateway (`services/api-bff`) does no money arithmetic (ADR-023): sums and percentages are made in the owning domain service. `test_routes_do_no_money_arithmetic` searches the route files for the plain text `Decimal`, `float(` and `round(`, so a comment with those words also fails it.
