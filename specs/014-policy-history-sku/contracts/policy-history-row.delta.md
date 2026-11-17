# Contract delta: policy history row carries the SKU

**Schema**: `packages/contracts/dto/policy_override_request.v1.schema.json` (stays v1; additive)

**Endpoints affected** (matrix entries owned through Agent 00): `GET /api/policy-overrides` (existing), and the `policy_history` card of `GET /admin/status`, which passes the list through unchanged.

## Change

```json
"sku": {
  "type": ["string", "null"],
  "minLength": 1,
  "description": "Current catalogue SKU of the product the request is about; null when the product is unknown or has no SKU. People see and type this; variant_id is for service calls only."
}
```

- Not added to `required` (older producers stay valid).
- `variant_id` unchanged.
- If the contract gate reports other fields the service already sends (for example `requested_at`), add only those, as optional.

## Contract tests (packages/contracts/tests)

| Case | Expected |
|------|----------|
| Row with `sku: "SYN-0005"` | valid |
| Row with `sku: null` | valid |
| Row without `sku` | valid (optional) |
| Row with `sku: 5` | invalid |
| Row with `sku: ""` | invalid |

## Service tests

- Procurement: the list returns the catalogue SKU for each row; null for a product absent from `product_refs`; null (not `""`) for a whitespace SKU.
- Gateway: the `policy_history` card carries `sku` through unchanged; the route-arithmetic guard test still passes.

## Web

- The `policy_history` row type gains `sku: string | null`; the column renders `sku` or the es-ES marker; no `variant_id` in the rendered output.
