# Agent and contributor rules

Mundo Mascotix Intelligence (MMI): inventory intelligence and weekly purchasing for a veterinary pharmacy and pet shop. Siweb360 is the ERP and system of record. This repository is **public**.

Authoritative documents: `.specify/memory/constitution.md` (v1.1.0), `specs/001-mmi-purchase-intelligence/` (spec, plan, tasks, contracts) and `docs/architecture/implementation-plan.md`.

## Non-negotiable rules

1. **Synthetic data only.** Never commit or use real exports, raw Siweb responses, real SKUs, products, suppliers, prices, quantities, names, e-mails, tenant/subscription/app IDs or resource names. Tests use fixtures from `packages/testing`.
2. **No secrets.** No tokens, keys, connection strings or real `.bicepparam`/`.tfvars` files. Commit `*.example` templates only. Secrets live in Azure Key Vault.
3. **Siweb is read-only except one write.** The connector (`services/siweb-connector`) allows only the GET allowlist in `specs/.../contracts/siweb-allowlist.md`. The single permitted write is `PUT /inventory/products/{id}/suppliers/{contact_id}` (supplier cost), only from `services/siweb-cost-writer`, only after buyer review with fresh MFA, always audited. Anything else is refused before a request is built.
4. **Humans decide purchases.** No autonomous writes, no self-approval (approver is not the creator or last editor), no order sending to suppliers.
5. **Money is `Decimal`** (never float). Store UTC plus the original timestamp string. Key products by Siweb `variant_id`.
6. **Never drop data silently.** Malformed or ambiguous records go to the quarantine/review list.
7. **Free-text notes are never parsed, stored or used in decisions** (only a `has_note` flag). `supplier_cif` is discarded before storage.
8. **UI is Spanish (es-ES) only**, with EUR and Spanish date/number formats; no hard-coded user-facing strings.
9. **Contract-first.** Change JSON Schemas in `packages/contracts` first; generated types follow. Each service owns its schema, role and migrations; no cross-schema SQL.
10. **Shared budget EUR 120/month.** Scale to zero, replica and job caps; reuse shared platform resources.

## Workflow

- Work from `specs/001-mmi-purchase-intelligence/tasks.md`; mark tasks `[X]` when done. Tests come before implementation within a story.
- Gate 0 items (research V1–V7) are open assumptions until verified; T135 (supplier-cost PUT semantics) must be verified on a non-production record before any write reaches the real ERP.
- Security posture and findings go to the internal wiki, not to this repo.
- PRs follow `.github/pull_request_template.md` (data, security, cost, contract impact).
