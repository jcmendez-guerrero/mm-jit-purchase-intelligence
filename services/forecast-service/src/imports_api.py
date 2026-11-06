"""T106 (service side) / T116: the import wizard's API. Buyers and admins only; every refusal carries a stable code."""

from __future__ import annotations

import os
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

from db.tables import seed_datasets
from fastapi import APIRouter, Depends, FastAPI, File, Form, HTTPException, Query, Response, UploadFile
from i18n import t
from mmi_common.errors import error_code
from pydantic import BaseModel
from runs.runner import RunConfig
from seeds import lifecycle as lc
from seeds import mapping as mp
from seeds import template as tpl
from seeds.dryrun import dry_run
from seeds.files import LocalSeedStore
from seeds.jobs import SYNC_ROWS, enqueue_validation
from seeds.jobs import list_jobs as job_list
from seeds.storage import SeedFileError
from sqlalchemy import create_engine, select
from sqlalchemy.engine import Connection, Engine
from upload_settings import load_limits

_engine: Engine | None = None
HTTP = {"import_file_too_large": 413, "import_decompression_limit": 413, "import_too_many_rows": 413, "import_type_not_allowed": 415, "import_mixed_origin": 409,
        "import_duplicate_file": 409, "import_dataset_state": 409, "import_nothing_to_activate": 409, "import_unknown_dataset": 404, "import_missing_column": 422,
        "import_mapping_name_taken": 409}


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = create_engine(os.environ["MMI_DATABASE_URL"], pool_pre_ping=True)
    return _engine


class ValidateBody(BaseModel):
    column_map: dict[str, str]
    mapping_id: str | None = None


class MappingBody(BaseModel):
    name: str
    column_map: dict[str, str]


class ActivateBody(BaseModel):
    acknowledge_duplicate: bool = False


def build_router(app: FastAPI) -> APIRouter:
    require: Callable[..., Any] = app.state.require_roles
    router = APIRouter(prefix="/imports")

    def conn_dep(engine: Engine = Depends(get_engine)) -> Iterator[Connection]:
        with engine.begin() as conn:
            yield conn

    def editor(principal: Any = Depends(require())) -> Any:
        if not ({"buyer", "admin"} & set(principal.roles)):
            raise HTTPException(403, "auth_forbidden_role")
        return principal

    def store() -> Any:
        s = getattr(app.state, "seed_store", None)
        if s is None:
            s = app.state.seed_store = LocalSeedStore(Path(os.environ.get("MMI_SEED_ROOT", "/tmp/mmi-forecast-seeds")))  # noqa: S108 - local default only
        return s

    def known_variants() -> tuple[set[int], list[dict[str, Any]]]:
        source = getattr(app.state, "series_source", None)
        if source is None:
            raise HTTPException(503, "not_configured")
        try:
            series = source.fetch()["series"]
        except Exception as exc:
            raise HTTPException(503, "inventory_unavailable") from exc
        return {int(s["variant_id"]) for s in series}, series

    def refuse(exc: Exception) -> HTTPException:
        return HTTPException(HTTP.get(error_code(exc), 422), error_code(exc))

    @router.get("/template")
    def template(format: str = Query(default="csv", pattern="^(csv|xlsx)$"), _p: Any = Depends(require())) -> Response:
        if format == "xlsx":
            return Response(tpl.template_xlsx(), media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            headers={"Content-Disposition": 'attachment; filename="plantilla-datos-predictivos.xlsx"'})
        return Response(tpl.template_csv(), media_type="text/csv; charset=utf-8", headers={"Content-Disposition": 'attachment; filename="plantilla-datos-predictivos.csv"'})

    @router.get("")
    def list_datasets(conn: Connection = Depends(conn_dep), _p: Any = Depends(require())) -> dict[str, Any]:
        return {"datasets": lc.list_datasets(conn)}

    @router.get("/mappings")
    def mappings(conn: Connection = Depends(conn_dep), _p: Any = Depends(require())) -> dict[str, Any]:
        return {"mappings": mp.list_mappings(conn), "fields": list(mp.CANONICAL), "required": list(mp.REQUIRED)}

    @router.post("/mappings", status_code=201)
    def save_mapping(body: MappingBody, conn: Connection = Depends(conn_dep), principal: Any = Depends(editor)) -> dict[str, Any]:
        try:
            return {"id": mp.save_mapping(conn, body.name, body.column_map, principal.subject)}
        except mp.MappingError as exc:
            raise refuse(exc) from exc

    @router.post("", status_code=201)
    def upload(file: UploadFile = File(...), name: str = Form(default=""), conn: Connection = Depends(conn_dep), principal: Any = Depends(editor)) -> dict[str, Any]:
        limits = load_limits()
        data = file.file.read(limits.max_bytes + 1)                    # never reads more than the cap allows
        try:
            return lc.register_upload(conn, store(), file.filename or "seed", data, name, principal.subject, limits)
        except SeedFileError as exc:
            raise refuse(exc) from exc

    @router.get("/jobs")
    def jobs(conn: Connection = Depends(conn_dep), _p: Any = Depends(require())) -> dict[str, Any]:
        return {"jobs": job_list(conn), "background_over_rows": SYNC_ROWS}

    @router.post("/{dataset_id}/validate")
    def validate(dataset_id: str, body: ValidateBody, response: Response, conn: Connection = Depends(conn_dep), principal: Any = Depends(editor)) -> dict[str, Any]:
        row = conn.execute(select(seed_datasets.c.row_count, seed_datasets.c.status).where(seed_datasets.c.id == dataset_id)).first()
        if row is not None and row.status in ("uploaded", "validated") and row.row_count > SYNC_ROWS:
            try:
                mp.validate_map(body.column_map)
            except mp.MappingError as exc:
                raise refuse(exc) from exc
            missing = mp.missing_required(body.column_map)
            if missing:
                raise HTTPException(422, "import_missing_column")
            queued = enqueue_validation(conn, dataset_id, body.column_map, principal.subject, body.mapping_id)
            response.status_code = 202                                                      # the buyer is told it went to the background
            return {"id": dataset_id, "queued": True, "job_id": queued["job_id"], "rows": row.row_count, "background_over_rows": SYNC_ROWS}
        known, _ = known_variants()
        try:
            return lc.validate_dataset(conn, store(), dataset_id, body.column_map, known, principal.subject, load_limits(), mapping_id=body.mapping_id)
        except (SeedFileError, lc.LifecycleError, mp.MappingError) as exc:
            raise refuse(exc) from exc

    @router.get("/{dataset_id}/quarantine")
    def quarantine(dataset_id: str, format: str = Query(default="json", pattern="^(json|csv|xlsx)$"), conn: Connection = Depends(conn_dep), _p: Any = Depends(require())) -> Any:
        rows = lc.quarantine_list(conn, dataset_id)
        if format == "json":
            return {"rows": rows}
        texts = [(r["row_no"], t(f"reason.{r['reason_key']}")) for r in rows]
        if format == "xlsx":
            return Response(tpl.quarantine_xlsx(texts), media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            headers={"Content-Disposition": 'attachment; filename="cuarentena.xlsx"'})
        return Response(tpl.quarantine_csv(texts), media_type="text/csv; charset=utf-8", headers={"Content-Disposition": 'attachment; filename="cuarentena.csv"'})

    @router.post("/{dataset_id}/dry-run")
    def dryrun(dataset_id: str, conn: Connection = Depends(conn_dep), _p: Any = Depends(editor)) -> dict[str, Any]:
        _, series = known_variants()
        if conn.execute(select(seed_datasets.c.id).where(seed_datasets.c.id == dataset_id)).first() is None:
            raise HTTPException(404, "import_unknown_dataset")
        return dry_run(conn, dataset_id, series, RunConfig().backtest.min_history)

    @router.post("/{dataset_id}/activate")
    def activate(dataset_id: str, body: ActivateBody | None = None, conn: Connection = Depends(conn_dep), principal: Any = Depends(editor)) -> dict[str, Any]:
        try:
            return lc.activate(conn, store(), dataset_id, principal.subject, acknowledge_duplicate=bool(body and body.acknowledge_duplicate))
        except (SeedFileError, lc.LifecycleError) as exc:
            raise refuse(exc) from exc

    @router.post("/rollback")
    def rollback(conn: Connection = Depends(conn_dep), principal: Any = Depends(editor)) -> dict[str, Any]:
        try:
            return lc.rollback(conn, store(), principal.subject)
        except lc.LifecycleError as exc:
            raise refuse(exc) from exc

    @router.post("/{dataset_id}/reject", status_code=204)
    def reject(dataset_id: str, conn: Connection = Depends(conn_dep), principal: Any = Depends(editor)) -> None:
        try:
            lc.reject(conn, dataset_id, principal.subject)
        except lc.LifecycleError as exc:
            raise refuse(exc) from exc

    return router
