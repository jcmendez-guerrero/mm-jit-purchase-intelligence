# ADR-017: Public-repository data policy

- Status: proposed
- Date: 2026-11-04

## Decision outcome

The repository is public. It may contain code, ADRs, generic documentation, `*.example` templates and synthetic fixtures. It must never contain tokens, keys, connection strings, real parameter files, tenant/subscription/app IDs, internal resource names, real products, suppliers, prices or quantities, raw ERP responses, e-mail addresses or names. Security posture and findings go to the internal wiki; `security/` holds methods only.

Enforcement: `.gitignore`, Gitleaks with custom rules, pre-commit hooks, GitHub secret-scanning push protection, PR template checklist.
