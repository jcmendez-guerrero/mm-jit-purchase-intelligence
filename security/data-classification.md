# Data classification scheme

Method only. Which concrete datasets sit in which class, and where they are stored, is recorded in the internal wiki.

| Class | Meaning | Examples (generic) | Handling |
|---|---|---|---|
| Public | Safe to publish | Code, ADRs, schemas, templates, synthetic fixtures | May live in this repository |
| Internal | Business data of the company | Stock levels, movements, costs, supplier terms, proposals | Azure only; never in the repository, logs or fixtures; access by role |
| Confidential | Personal or commercially sensitive | Staff or customer identifiers, supplier tax IDs, free-text notes | Not collected (discarded before storage) unless a documented need exists |
| Secret | Grants access | Tokens, keys, connection strings | Azure Key Vault only; per-identity access; never logged |

Rules:

1. Data moves down a class (e.g. to a fixture) only as aggregate ratios, never as real rows or identifiers.
2. Raw source payloads are Internal, stripped of Confidential fields first, and deleted after the retention period.
3. Logs and metrics carry no Secret or Confidential data; correlation IDs only.
