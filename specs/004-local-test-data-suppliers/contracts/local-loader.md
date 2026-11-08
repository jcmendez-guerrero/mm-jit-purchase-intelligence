# Contract: Local Loader (command, local HTTP, BFF routes)

Available only in the local environment. Absent from cloud images; the BFF routes exist only when `MMI_LOCAL_LOADER=1` and `MMI_ENV` is not `prod`/`staging`; otherwise they answer 404 and a security event is recorded.

## Command

```bash
python -m export_loader check --dir data/local-exports      # validate files, print counts, change nothing
python -m export_loader load  --dir data/local-exports      # inventory + movements (+ suppliers if present), then trigger a sync
python -m export_loader load  --dir packages/testing/fixtures/exports   # synthetic set
python -m export_loader wipe                                  # delete loader state and local database contents
```

Files are loaded in the order suppliers, inventory, movements (the inventory load links products to the suppliers it names). The kinds accepted by the HTTP app and the BFF routes are `suppliers`, `inventory` and `movements`.

Rules: refuses any `--dir` inside the repository tree except `packages/testing/fixtures/exports`; refuses to run if the target database or queue endpoint is not local; prints counts only (no row content); exit code non-zero if anything is quarantined beyond the configured threshold.

## Load result (shared by command, HTTP and screen)

```json
{
  "run_id": "uuid",
  "kind": "inventory | movements | suppliers",
  "file_sha256": "…",
  "rows": 0,
  "loaded": 0, "updated": 0, "unchanged": 0,
  "quarantined": 0, "excluded": 0, "services": 0,
  "differences": 0,
  "review": [{"row": 12, "code": "unmapped_reason", "detail": "…"}],
  "interpretations": {"tax_included_rows": 0, "tax_excluded_rows": 0, "timezone": "Europe/Madrid"}
}
```
Invariant: `loaded + updated + unchanged + quarantined + excluded + services == rows`. Review `detail` never contains note text, tax IDs, bank data or personal names.

## Local HTTP (loader app, override file `infra/compose.local-data.yaml`, port local only)

| Method | Path | Purpose |
|---|---|---|
| POST | `/load/{kind}` | multipart upload of one file; an inventory load requires `acknowledge_interpretation=true` after a check has shown the tax and price interpretation; returns the load result; file is held in memory or a private temp folder and deleted afterwards |
| POST | `/check/{kind}` | dry run, same result with nothing written |
| GET | `/state` | counts only: last runs, SKU map size |
| DELETE | `/state` | wipe |

## Sync trigger

After a successful inventory or movements load, the command and the loader app call a local-only endpoint on the connector, `POST /internal/local-sync` (service identity, mounted only when `MMI_LOCAL_LOADER=1`, runs the collection job in the same process, and only against the mock host; refused otherwise). The connector has no other HTTP trigger today, and the real ERP is never reachable through this path.

## Authentication

Every call uses an audience-scoped token from the local issuer: audience `local-loader` for BFF → loader, and the loader's own principal for loader → inventory-service and procurement-service. Missing, expired or wrong-audience tokens answer 401/403 with `local_load_unauthenticated`.

## BFF routes (roles: buyer, admin)

| Method | Path | Notes |
|---|---|---|
| GET | `/local-load/capability` | `{"enabled": true|false}`; the SPA hides the screen when false or 404 |
| POST | `/local-load/{kind}/check` | proxies to the loader app |
| POST | `/local-load/{kind}` | proxies; upload limits from the existing upload settings; requires an `Idempotency-Key` |
| GET | `/local-load/runs` | last results |
| GET | `/local-load/review` | review items held by the loader (rows it could not express), labelled source `loader`; the data-quality screen merges them with platform quarantine items |

Refusals carry stable codes: `local_load_disabled`, `local_load_file_too_large`, `local_load_type_not_allowed`, `local_load_signature_mismatch`, `local_load_macros_or_links`, `local_load_too_many_rows`, `local_load_not_local_target`.
