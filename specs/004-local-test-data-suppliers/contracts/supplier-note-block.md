# Contract: Supplier Conditions Block in the ERP Note

**Status: designed and unit-tested, operation disabled until Gate 0 (G0-N1..N3).** Constitution v1.3.0, Principle I. The application is the source of truth.

## Block format

A single block delimited by marker lines, anywhere in the note (appended at the end if absent):

```
[[MMI:BEGIN v1]]
{"v":1,"lead_time_days":3,"min_order_value":"150.00","min_qty":null,"free_delivery_threshold":"300.00","delivery_charge":"5.00","order_days":[1,3],"currency":"EUR","updated":"2026-11-08T10:00:00Z","hash":"…"}
[[MMI:END]]
```

- JSON on one line; money as decimal strings; `hash` is a SHA-256 of the canonical content, used to detect discrepancies without parsing anything else.
- Markers are exact ASCII. Exactly one pair is valid. Zero pairs → append. More than one begin or end, or a begin without end → **refuse** and raise a review item.

## Merge rules (writer)

1. Read the current note immediately before writing.
2. Locate the block; replace only the characters between and including the markers, or append (with one separating line break) when absent. Every other character is byte-identical.
3. If the note differs from the read taken at the start of the operation → abort and re-evaluate (no overwrite).
4. After the write, read back and verify the block hash.
5. Hold the note in memory only for the operation; log only hashes and lengths; keep only `has_note`.

## Discrepancy detection

Compare `hash` in the ERP block with the application's current hash and the ERP's structured payment terms with the application's `payment_terms_days`. States: `in_sync`, `pending` (application changed, not yet written), `discrepancy` (ERP block differs from both last written and desired), `failed`, `pending_link`. A discrepancy shows both values to the buyer or admin, who chooses; nothing is overwritten automatically.

## Test obligations (phase 7)

Property tests: arbitrary note text (including line breaks, non-ASCII, marker-like text inside other content) round-trips unchanged outside the block; damaged and duplicated markers are refused; idempotent when nothing changed; size within the Gate 0 length limit. The allowlist test asserts the operation builds **no** request while its path is `TBD`.
