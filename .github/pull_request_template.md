## What and why

<!-- Link the task IDs from specs/001-mmi-purchase-intelligence/tasks.md -->

## Checklist

**Data**
- [ ] No real exports, raw API responses, SKUs, suppliers, prices, names or e-mails; fixtures are synthetic
- [ ] Fields not needed are discarded before storage (`supplier_cif`, free-text notes)

**Security**
- [ ] No secrets, tenant/subscription/app IDs or real `.bicepparam`/`.tfvars` values
- [ ] Siweb access still limited to the allowlists (reader: GET list; writer: supplier-cost PUT only) and tests prove refusals
- [ ] Authorisation and separation-of-duties rules unchanged or tested

**Cost**
- [ ] No new always-on resource; scale-to-zero, replica and job caps respected; impact on the shared EUR 120/month noted

**Contracts**
- [ ] JSON Schemas and OpenAPI updated first; compatibility check and contract tests pass
- [ ] Breaking change has a versioned type and a rollout note

**Quality**
- [ ] Tests added or updated (including failure and duplicate handling)
- [ ] User-facing text is in Spanish via translation keys
- [ ] Constitution and applicable ADRs checked
