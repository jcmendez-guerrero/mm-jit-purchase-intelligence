"""T112 + T104: dataset lifecycle - register, validate, activate, roll back. Each transition is one transaction, audited, and requests a run.

uploaded -> validated -> active -> superseded (when a newer one is activated) ; active -> rolled_back (restores the previous one) ; any -> rejected.
Rows are never deleted by a rollback; only the active pointer moves. A repeated file (same checksum) needs an explicit decision to activate.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Collection, Mapping
from datetime import UTC, date, datetime
from typing import Any, Protocol

from audit import append as audit
from db.tables import import_jobs, outbox, seed_datasets, seed_quarantine, seed_rows
from mmi_common.bus import new_envelope
from mmi_common.outbox import enqueue
from mmi_common.time import get_correlation_id, set_correlation_id
from sqlalchemy import delete, func, insert, select, update
from sqlalchemy.engine import Connection, Row
from sqlalchemy.exc import IntegrityError
from upload_settings import ParseLimits

from seeds import mapping as mp
from seeds.export_shapes import erp_export_shape
from seeds.parsers import parse
from seeds.storage import SeedFileError, detect_format, sha256_hex, store_private
from seeds.validation import validate_rows

EVENT_TYPE = "forecast.seed.activated.v1"
PREVIEW_ROWS = 20


class BlobStore(Protocol):
    def put(self, name: str, data: bytes) -> str: ...
    def get(self, ref: str) -> bytes: ...


class LifecycleError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def _get(conn: Connection, dataset_id: str) -> Row[Any]:
    r = conn.execute(select(seed_datasets).where(seed_datasets.c.id == dataset_id)).first()
    if r is None:
        raise LifecycleError("import_unknown_dataset")
    return r


def _job(conn: Connection, dataset_id: str, stage: str, now: datetime, error: str | None = None) -> None:
    conn.execute(insert(import_jobs).values(id=str(uuid.uuid4()), dataset_id=dataset_id, stage=stage, state="failed" if error else "done", started_at=now, finished_at=now, error_key=error))


def duplicate_of(conn: Connection, sha: str, exclude: str | None = None) -> str | None:
    q = select(seed_datasets.c.id).where(seed_datasets.c.file_sha256 == sha, seed_datasets.c.status.in_(("active", "superseded", "rolled_back")))
    if exclude:
        q = q.where(seed_datasets.c.id != exclude)
    r = conn.execute(q.limit(1)).first()
    return None if r is None else str(r.id)


def register_upload(conn: Connection, store: BlobStore, filename: str, data: bytes, name: str, uploader: str, limits: ParseLimits, now: datetime | None = None) -> dict[str, Any]:
    """Checks the file, keeps the original privately and returns the headers, a suggested mapping and a short preview. No rows are stored yet."""
    now = now or datetime.now(UTC)
    fmt = detect_format(filename, data, limits)
    headers, rows = parse(fmt, data, limits)
    if erp_export_shape(headers):
        raise SeedFileError("import_erp_export_refused")                # ERP exports are local-only; a seed file is the owner's own estimate
    sha = sha256_hex(data)
    did = str(uuid.uuid4())
    version = int(conn.execute(select(func.max(seed_datasets.c.version))).scalar() or 0) + 1
    ref = store_private(store, did, filename, data)
    suggestion = mp.suggest(headers)
    conn.execute(insert(seed_datasets).values(id=did, version=version, name=(name or filename)[:200], status="uploaded", origin="synthetic", file_sha256=sha, file_ref=ref,
                                              uploader=uploader, uploaded_at=now, accepted_count=0, quarantined_count=0, rejected_count=0, row_count=len(rows)))
    dup = duplicate_of(conn, sha, did)
    audit(conn, uploader, "seed.uploaded", "seed_dataset", did, after={"version": version, "sha256": sha, "rows": len(rows), "format": fmt, "duplicate_of": dup}, now=now)
    _job(conn, did, "parse", now)
    preview = mp.apply(suggestion, rows[:PREVIEW_ROWS])
    return {"id": did, "version": version, "status": "uploaded", "format": fmt, "headers": headers, "row_count": len(rows), "suggested_mapping": suggestion,
            "missing": mp.missing_required(suggestion), "preview": preview, "duplicate_of": dup, "sha256": sha}


def validate_dataset(conn: Connection, store: BlobStore, dataset_id: str, column_map: dict[str, str], known_variants: set[int], actor: str, limits: ParseLimits,
                     today: date | None = None, mapping_id: str | None = None, now: datetime | None = None, record_job: bool = True,
                     *, sku_map: Mapping[str, int | Collection[int]]) -> dict[str, Any]:
    """Parses the stored original with the chosen mapping and stores accepted rows and quarantined ones. Safe to repeat (idempotent per dataset)."""
    now = now or datetime.now(UTC)
    ds = _get(conn, dataset_id)
    if ds.status not in ("uploaded", "validated"):
        raise LifecycleError("import_dataset_state")
    mp.validate_map(column_map)
    missing = mp.missing_required(column_map)
    if missing:
        raise SeedFileError("import_missing_column", ",".join(missing))
    data = store.get(ds.file_ref)
    fmt = "xlsx" if data.startswith(b"PK\x03\x04") else "csv"
    _headers, rows = parse(fmt, data, limits)
    result = validate_rows(mp.apply(column_map, rows), known_variants, today, sku_map=sku_map)
    conn.execute(delete(seed_rows).where(seed_rows.c.dataset_id == dataset_id))
    conn.execute(delete(seed_quarantine).where(seed_quarantine.c.dataset_id == dataset_id))
    if result.accepted:
        conn.execute(insert(seed_rows), [{"dataset_id": dataset_id, "row_no": a.row_no, "variant_id": a.variant_id, "sku": a.sku, "day": a.day, "day_text": a.day_text, "warehouse_external_id": a.warehouse,
                                          "quantity": a.quantity, "kind": a.kind, "provenance_label": a.provenance} for a in result.accepted])
    if result.quarantined:
        conn.execute(insert(seed_quarantine), [{"dataset_id": dataset_id, "row_no": q.row_no, "reason_key": q.reason_key, "reason_params": q.params, "raw_row_hash": q.raw_hash}
                                               for q in result.quarantined])
    kinds: dict[str, int] = {}
    for a in result.accepted:
        kinds[a.kind] = kinds.get(a.kind, 0) + 1
    conn.execute(update(seed_datasets).where(seed_datasets.c.id == dataset_id).values(
        status="validated", origin=result.origin, accepted_count=len(result.accepted), quarantined_count=len(result.quarantined), rejected_count=0, kind_summary=kinds, mapping_id=mapping_id, validated_by=actor, mapping_chosen_by=actor))
    audit(conn, actor, "seed.validated", "seed_dataset", dataset_id, after={"accepted": len(result.accepted), "quarantined": len(result.quarantined), "origin": result.origin}, now=now)
    if record_job:
        _job(conn, dataset_id, "validate", now)
    return {"id": dataset_id, "status": "validated", "origin": result.origin, "accepted": len(result.accepted), "quarantined": len(result.quarantined), "kinds": kinds}


def quarantine_list(conn: Connection, dataset_id: str) -> list[dict[str, Any]]:
    return [{"row_no": q.row_no, "reason_key": q.reason_key, "params": q.reason_params or {}}
            for q in conn.execute(select(seed_quarantine).where(seed_quarantine.c.dataset_id == dataset_id).order_by(seed_quarantine.c.row_no)).all()]


def reject(conn: Connection, dataset_id: str, actor: str, now: datetime | None = None) -> None:
    ds = _get(conn, dataset_id)
    if ds.status == "active":
        raise LifecycleError("import_dataset_state")
    conn.execute(update(seed_datasets).where(seed_datasets.c.id == dataset_id).values(status="rejected"))
    audit(conn, actor, "seed.rejected", "seed_dataset", dataset_id, before={"status": ds.status}, after={"status": "rejected"}, now=now)


def _announce(conn: Connection, writer: Any, ds: Row[Any], action: str) -> None:
    payload = json.dumps({"dataset_id": ds.id, "version": ds.version, "action": action}, sort_keys=True, separators=(",", ":")).encode()
    uri = writer.put(f"events/seed/{ds.id}.{action}.json", payload)
    enqueue(conn, outbox, new_envelope(EVENT_TYPE, f"{ds.id}.{action}", payload, uri, get_correlation_id() or set_correlation_id()))


def active_dataset(conn: Connection) -> Row[Any] | None:
    return conn.execute(select(seed_datasets).where(seed_datasets.c.status == "active")).first()


# FR-033: a reason is a choice from a fixed list plus an optional short detail. These lists are the enums of packages/contracts/dto/seed_dataset.v1.schema.json (a test keeps them equal).
ROLLBACK_REASONS = ("wrong_figures", "wrong_file", "test", "replaced_by_newer", "other")
SELF_ACTIVATION_REASONS = ("only_person", "urgent", "other")
MAX_DETAIL = 100


def _reason(code: str | None, detail: str | None, allowed: tuple[str, ...]) -> tuple[str, str | None]:
    """The chosen code and the tidied detail (blanks collapsed, None when empty). A missing code and an unknown code or a too long detail are different refusals."""
    if not (code or "").strip():
        raise LifecycleError("import_reason_required")
    tidy = " ".join((detail or "").split())
    if code not in allowed or len(tidy) > MAX_DETAIL or not tidy.isprintable():        # a NUL or other control character would also break the database write
        raise LifecycleError("import_reason_invalid")
    return code, tidy or None


def activate(conn: Connection, writer: Any, dataset_id: str, actor: str, *, acknowledge_duplicate: bool = False, now: datetime | None = None,
             is_admin: bool = False, reason_code: str | None = None, reason_detail: str | None = None) -> dict[str, Any]:
    """One transaction: the previous active dataset becomes superseded, this one active, the audit entry and the run request are written together.

    The uploader and whoever chose the mapping or ran validation cannot approve. The one exception is an owner/admin with a listed reason (a one-person shop): it is
    allowed and audited apart as ``seed.self_activated`` (the audit entry holds the reason code, never the free-text detail).
    """
    now = now or datetime.now(UTC)
    ds = _get(conn, dataset_id)
    if ds.status != "validated":
        raise LifecycleError("import_dataset_state")
    self_activation = actor in {ds.uploader, ds.validated_by, ds.mapping_chosen_by}
    why: tuple[str, str | None] | None = None
    if self_activation:
        if not is_admin:
            raise LifecycleError("import_self_approval")
        why = _reason(reason_code, reason_detail, SELF_ACTIVATION_REASONS)
    if ds.accepted_count == 0:
        raise LifecycleError("import_nothing_to_activate")
    if duplicate_of(conn, ds.file_sha256, dataset_id) and not acknowledge_duplicate:
        raise LifecycleError("import_duplicate_file")
    current = active_dataset(conn)
    if current is not None and current.origin != ds.origin:
        raise SeedFileError("import_mixed_origin")                    # synthetic and real data never become active together
    if current is not None:
        conn.execute(update(seed_datasets).where(seed_datasets.c.id == current.id).values(status="superseded"))
    try:
        conn.execute(update(seed_datasets).where(seed_datasets.c.id == dataset_id).values(status="active", activated_by=actor, activated_at=now, supersedes_id=None if current is None else current.id,
                                                                                   self_activation_reason_code=why[0] if why else None, self_activation_reason_detail=why[1] if why else None))
    except IntegrityError as exc:                                     # another request activated a dataset first (one active dataset at a time)
        raise LifecycleError("import_conflict") from exc
    audit(conn, actor, "seed.self_activated" if self_activation else "seed.activated", "seed_dataset", dataset_id, before={"previous": None if current is None else current.id},
          after={"version": ds.version, "accepted": ds.accepted_count, "duplicate_acknowledged": bool(acknowledge_duplicate), **({"reason_code": why[0]} if why else {})}, now=now)
    _announce(conn, writer, ds, "activated")
    _job(conn, dataset_id, "activate", now)
    return {"id": dataset_id, "version": ds.version, "status": "active", "superseded": None if current is None else current.id}


def rollback(conn: Connection, writer: Any, actor: str, now: datetime | None = None, *, reason_code: str | None = None, reason_detail: str | None = None) -> dict[str, Any]:
    """The active dataset becomes rolled_back and the one it superseded becomes active again. No rows are deleted. A listed reason is required; the audit trail holds the code, never the detail."""
    now = now or datetime.now(UTC)
    code, detail = _reason(reason_code, reason_detail, ROLLBACK_REASONS)
    cur = active_dataset(conn)
    if cur is None:
        raise LifecycleError("import_dataset_state")
    prev = None if cur.supersedes_id is None else _get(conn, cur.supersedes_id)
    done = conn.execute(update(seed_datasets).where(seed_datasets.c.id == cur.id, seed_datasets.c.status == "active").values(status="rolled_back", rollback_reason_code=code, rollback_reason_detail=detail))
    if done.rowcount != 1:                                              # another rollback (or an activation) finished first: exactly one of them wins
        raise LifecycleError("import_conflict")
    if prev is not None:
        conn.execute(update(seed_datasets).where(seed_datasets.c.id == prev.id).values(status="active"))
    audit(conn, actor, "seed.rolled_back", "seed_dataset", cur.id, before={"version": cur.version}, after={"restored": None if prev is None else prev.id, "reason_code": code}, now=now)
    _announce(conn, writer, cur, "rolled_back")
    _job(conn, cur.id, "rollback", now)
    return {"id": cur.id, "status": "rolled_back", "restored": None if prev is None else prev.id}


def record_dry_run(conn: Connection, dataset_id: str, actor: str, result: dict[str, Any], now: datetime | None = None) -> None:
    """FR-029: the dry run changes nothing stored, but who ran it and what it compared is audited (counts only: no rows, no file contents)."""
    ds = _get(conn, dataset_id)
    audit(conn, actor, "seed.dry_run", "seed_dataset", dataset_id, after={"version": ds.version, "compared_with": result.get("compared_with"), "rows": result.get("rows")}, now=now or datetime.now(UTC))


def list_datasets(conn: Connection, *, is_admin: bool = False) -> list[dict[str, Any]]:
    """The dataset list. The chosen reasons are shown to everyone; the free-text details only to admins (FR-033)."""
    def item(r: Row[Any]) -> dict[str, Any]:
        out = {"id": r.id, "version": r.version, "name": r.name, "status": r.status, "origin": r.origin, "uploader": r.uploader, "uploaded_at": r.uploaded_at.isoformat(), "row_count": r.row_count,
             "activated_by": r.activated_by, "activated_at": r.activated_at.isoformat() if r.activated_at else None, "accepted": r.accepted_count, "quarantined": r.quarantined_count,
             "kinds": r.kind_summary or {}, "validated_by": r.validated_by, "rollback_reason_code": r.rollback_reason_code,
               "self_activation_reason_code": r.self_activation_reason_code, "self_activated": bool(r.self_activation_reason_code)}
        if is_admin:
            out |= {"rollback_reason_detail": r.rollback_reason_detail, "self_activation_reason_detail": r.self_activation_reason_detail}
        return out

    return [item(r) for r in conn.execute(select(seed_datasets).order_by(seed_datasets.c.version.desc())).all()]
