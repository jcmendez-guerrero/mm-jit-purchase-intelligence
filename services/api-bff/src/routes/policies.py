"""T087 / T091 / T095: the policy console. Three independently revisioned sections, composed here and owned by their services:

* purchasing  (procurement-service): service levels, safety stock, min/max, cadence, budget caps, stocking settings, override requests
* demand      (inventory-service): demand exclusions, censoring rules, clinical criticality, category history
* forecast    (forecast-service): approved model parameters

The BFF checks roles and forwards the signed-in user with the revision the editor read (If-Match); it holds no business rule.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import httpx
from auth.session import SessionData
from clients.forecast import ForecastClient
from clients.inventory import InventoryClient
from clients.procurement import ProcurementClient
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from routes.api import get_inventory_client, get_procurement_client
from routes.rbac import log_refusal, require_roles

router = APIRouter()
_forecast = ForecastClient()
ANY = ("viewer", "buyer", "approver", "admin")
POLICY_PATHS = ("/api/policies", "/api/budget-caps", "/api/stocking", "/api/policy-overrides", "/api/demand-rules", "/api/parameters", "/api/products/")


AUDIT_PAGE = 50
AUDIT_SOURCE_LIMIT = 500
MADRID = ZoneInfo("Europe/Madrid")
AUDIT_SCOPES = {"policy": ("policy.",), "budget": ("budget_cap.",), "safety_stock": ("stocking.", "policy_override."),
                "demand": ("demand_exclusion.", "censoring_rule.", "criticality."), "forecast": ("parameter.",), "access": ("access.",)}


def _madrid_day(at: str) -> date:
    """The calendar day a stored UTC instant falls on for the people reading the audit (es-ES, rule 8)."""
    d = datetime.fromisoformat(at)
    return (d if d.tzinfo else d.replace(tzinfo=UTC)).astimezone(MADRID).date()


def _day_start_utc(day: date) -> str:
    return datetime.combine(day, time.min, MADRID).astimezone(UTC).isoformat()


def _need_fresh_mfa(request: Request, session: SessionData) -> None:
    """Budget caps and global-scope values move money or stock rules for the whole business: they need a second factor from the last 5 minutes (feature 011 FR-012)."""
    if not session.is_mfa_fresh(max_age_seconds=300):
        log_refusal(request, session.user_id, session.roles, [], "forbidden_mfa_stale")
        raise HTTPException(status_code=403, detail="auth_mfa_stale")


def _without_variant_ids(rows: Any) -> Any:
    """People see SKUs; the ERP variant id stays inside the platform."""
    if isinstance(rows, list):
        return [{k: v for k, v in r.items() if k != "variant_id"} if isinstance(r, dict) else r for r in rows]
    if isinstance(rows, dict):
        return {k: v for k, v in rows.items() if k != "variant_id"}
    return rows


def get_forecast_client() -> ForecastClient:
    return _forecast


async def _section(call: Any) -> dict[str, Any]:
    """One section failing must not hide the others: the console shows which part is unavailable."""
    try:
        return {"ok": True, "data": await call}
    except httpx.HTTPStatusError as exc:
        return {"ok": False, "error": "downstream_refused" if 400 <= exc.response.status_code < 500 else "downstream_unavailable"}
    except (httpx.TransportError, RuntimeError):
        return {"ok": False, "error": "downstream_unavailable"}


@router.get("/policy-console")
async def policy_console(
    session: SessionData = Depends(require_roles("viewer")),
    proc: ProcurementClient = Depends(get_procurement_client),
    inv: InventoryClient = Depends(get_inventory_client),
    fc: ForecastClient = Depends(get_forecast_client),
) -> dict[str, Any]:
    r, u = session.roles, session.user_id
    purchasing = await _section(proc.forward("GET", "/policies", user_id=u, roles=r))
    if purchasing.get("ok") and isinstance(purchasing["data"], dict):
        purchasing["data"]["policies"] = _without_variant_ids(purchasing["data"].get("policies", []))
    return {
        "purchasing": purchasing,
        "demand": await _section(inv.forward("GET", "/demand-rules", user_id=u, roles=r)),
        "forecast": await _section(fc.forward("GET", "/parameters", user_id=u, roles=r)),
    }


# ---- purchasing -----------------------------------------------------------------------------------------------------------------

@router.get("/policies/{scope}/{key}")
async def get_policy(scope: str, key: str, session: SessionData = Depends(require_roles("viewer")), proc: ProcurementClient = Depends(get_procurement_client)) -> Any:
    return await proc.forward("GET", f"/policies/{scope}/{key}", user_id=session.user_id, roles=session.roles)


@router.put("/policies/{scope}/{key}")
async def put_policy(request: Request, scope: str, key: str, body: dict[str, Any], if_match: str | None = Header(default=None),
                     session: SessionData = Depends(require_roles("buyer")), proc: ProcurementClient = Depends(get_procurement_client)) -> Any:
    if scope == "global":
        _need_fresh_mfa(request, session)                       # the role is checked first, like the cost operations
    return await proc.forward("PUT", f"/policies/{scope}/{key}", json=body, user_id=session.user_id, roles=session.roles, if_match=if_match)


@router.delete("/policies/{scope}/{key}")
async def clear_policy(request: Request, scope: str, key: str, if_match: str | None = Header(default=None), session: SessionData = Depends(require_roles("buyer")),
                       proc: ProcurementClient = Depends(get_procurement_client)) -> Any:
    """Removes an override (a new revision with every field empty); global scope needs the same fresh second factor as saving it."""
    if scope == "global":
        _need_fresh_mfa(request, session)
    return await proc.forward("DELETE", f"/policies/{scope}/{key}", user_id=session.user_id, roles=session.roles, if_match=if_match)


@router.post("/policies/{scope}/{key}/preview")
async def preview_policy(scope: str, key: str, body: dict[str, Any], session: SessionData = Depends(require_roles("buyer")),
                         proc: ProcurementClient = Depends(get_procurement_client)) -> Any:
    out = await proc.forward("POST", f"/policies/{scope}/{key}/preview", json=body, user_id=session.user_id, roles=session.roles)
    if isinstance(out, dict) and "affected" in out:
        out["affected"] = _without_variant_ids(out["affected"])
    return out


@router.put("/budget-caps")
async def put_budget(request: Request, body: dict[str, Any], if_match: str | None = Header(default=None), session: SessionData = Depends(require_roles("buyer")),
                     proc: ProcurementClient = Depends(get_procurement_client)) -> Any:
    _need_fresh_mfa(request, session)
    return await proc.forward("PUT", "/budget-caps", json=body, user_id=session.user_id, roles=session.roles, if_match=if_match)


@router.get("/products/{sku}/effective-policy")
async def effective_policy(sku: str, session: SessionData = Depends(require_roles("viewer")), proc: ProcurementClient = Depends(get_procurement_client),
                           inv: InventoryClient = Depends(get_inventory_client)) -> Any:
    """Each rule with the value in force and where it comes from; the product's segments come from inventory, the values from procurement."""
    seg = await inv.forward("GET", f"/products/{sku}/segments", user_id=session.user_id, roles=session.roles)
    return await proc.forward("GET", f"/products/{sku}/effective-policy", params={"segments": ",".join(seg.get("segments", []))}, user_id=session.user_id, roles=session.roles)


@router.get("/policy-audit")
async def policy_audit(
    session: SessionData = Depends(require_roles("admin")), proc: ProcurementClient = Depends(get_procurement_client),
    inv: InventoryClient = Depends(get_inventory_client), fc: ForecastClient = Depends(get_forecast_client),
    scope: str | None = Query(default=None, pattern="^(policy|budget|safety_stock|demand|forecast|access)$"),
    outcome: str | None = Query(default=None, pattern="^(accepted|refused)$"),
    from_day: date | None = Query(default=None, alias="from"), to_day: date | None = Query(default=None, alias="to"), page: int = Query(default=1, ge=1, le=1000),
) -> dict[str, Any]:
    """Who changed which rule, and who was refused: accepted changes from the services that own the rules, refusals from the gateway's own audit.

    Filtered by what was changed (scope), the outcome and a date range, newest first, 50 rows a page.
    """
    from routes.admin_roles import get_store

    prefixes = AUDIT_SCOPES.get(scope or "", ())
    # The services apply the filters before their row limit, so an old match is never cut by newer rows of another kind.
    params: dict[str, Any] = {"limit": AUDIT_SOURCE_LIMIT, **({"prefix": ",".join(prefixes)} if prefixes else {}), **({"outcome": outcome} if outcome else {}),
                              **({"since": _day_start_utc(from_day)} if from_day else {}), **({"until": _day_start_utc(to_day + timedelta(days=1))} if to_day else {})}
    items: list[dict[str, Any]] = []
    unavailable: list[str] = []
    truncated: list[str] = []
    for name, client in (("procurement", proc), ("inventory", inv), ("forecast", fc)):
        try:
            got = (await client.forward("GET", "/policy-audit", params=params, user_id=session.user_id, roles=session.roles)).get("items", [])
        except (httpx.HTTPError, RuntimeError):
            unavailable.append(name)
            continue
        items += got
        if len(got) >= AUDIT_SOURCE_LIMIT:
            truncated.append(name)
    for e in get_store().audit_view():
        if e["action"] == "access.refused" and any(f" {p}" in f" {e['target_user']}" for p in POLICY_PATHS):
            items.append({"at": e["timestamp"], "actor": e["actor"], "action": "access.refused", "entity": "access", "entity_id": e["target_user"], "outcome": "refused",
                          "reason_code": e["refusal_reason"]})
    items = [i for i in items
             if (not prefixes or i["action"].startswith(prefixes)) and (outcome is None or i.get("outcome") == outcome)
             and (from_day is None or _madrid_day(i["at"]) >= from_day) and (to_day is None or _madrid_day(i["at"]) <= to_day)]
    items.sort(key=lambda i: i["at"], reverse=True)
    start = (page - 1) * AUDIT_PAGE
    return {"items": items[start:start + AUDIT_PAGE], "total": len(items), "page": page, "page_size": AUDIT_PAGE, "unavailable": unavailable, "truncated": truncated}


# Stocking, override and recommendation routes take the SKU (feature 011, FR-018): the ERP variant id is resolved inside procurement and never shown.

@router.get("/stocking/{sku}")
async def get_stocking(sku: str, session: SessionData = Depends(require_roles("viewer")), proc: ProcurementClient = Depends(get_procurement_client)) -> Any:
    return _without_variant_ids(await proc.forward("GET", f"/stocking/{sku}", user_id=session.user_id, roles=session.roles))


@router.put("/stocking/{sku}")
async def put_stocking(sku: str, body: dict[str, Any], if_match: str | None = Header(default=None), session: SessionData = Depends(require_roles("buyer")),
                       proc: ProcurementClient = Depends(get_procurement_client)) -> Any:
    return await proc.forward("PUT", f"/stocking/{sku}", json=body, user_id=session.user_id, roles=session.roles, if_match=if_match)


@router.get("/policy-overrides")
async def list_overrides(status: str = "pending", session: SessionData = Depends(require_roles("viewer")), proc: ProcurementClient = Depends(get_procurement_client)) -> Any:
    return _without_variant_ids(await proc.forward("GET", "/policy-overrides", params={"status": status}, user_id=session.user_id, roles=session.roles))


@router.get("/policy-overrides/recommendation/{sku}")
async def recommendation(sku: str, session: SessionData = Depends(require_roles("viewer")), proc: ProcurementClient = Depends(get_procurement_client)) -> Any:
    return _without_variant_ids(await proc.forward("GET", f"/policy-overrides/recommendation/{sku}", user_id=session.user_id, roles=session.roles))


@router.post("/policy-overrides", status_code=201)
async def create_override(body: dict[str, Any], session: SessionData = Depends(require_roles("buyer")), proc: ProcurementClient = Depends(get_procurement_client)) -> Any:
    return _without_variant_ids(await proc.forward("POST", "/policy-overrides", json=body, user_id=session.user_id, roles=session.roles))


@router.post("/policy-overrides/{rid}/approve")
async def approve_override(rid: str, session: SessionData = Depends(require_roles("approver")), proc: ProcurementClient = Depends(get_procurement_client)) -> Any:
    return _without_variant_ids(await proc.forward("POST", f"/policy-overrides/{rid}/approve", json={}, user_id=session.user_id, roles=session.roles))


@router.post("/policy-overrides/{rid}/reject")
async def reject_override(rid: str, session: SessionData = Depends(require_roles("approver")), proc: ProcurementClient = Depends(get_procurement_client)) -> Any:
    return _without_variant_ids(await proc.forward("POST", f"/policy-overrides/{rid}/reject", json={}, user_id=session.user_id, roles=session.roles))


@router.post("/policy-overrides/{rid}/revert")
async def revert_override(rid: str, session: SessionData = Depends(require_roles("buyer", "approver")), proc: ProcurementClient = Depends(get_procurement_client)) -> Any:
    return _without_variant_ids(await proc.forward("POST", f"/policy-overrides/{rid}/revert", json={}, user_id=session.user_id, roles=session.roles))


# ---- demand rules, criticality, category history (inventory) --------------------------------------------------------------------

@router.get("/criticality")
async def criticality(session: SessionData = Depends(require_roles("viewer")), inv: InventoryClient = Depends(get_inventory_client)) -> Any:
    return await inv.forward("GET", "/criticality", user_id=session.user_id, roles=session.roles)


@router.put("/products/{sku}/criticality")
async def set_criticality(sku: str, body: dict[str, Any], session: SessionData = Depends(require_roles("buyer")), inv: InventoryClient = Depends(get_inventory_client)) -> Any:
    return await inv.forward("PUT", f"/products/{sku}/criticality", json=body, user_id=session.user_id, roles=session.roles)


@router.post("/demand-rules/exclusions", status_code=201)
async def add_exclusion(body: dict[str, Any], session: SessionData = Depends(require_roles("buyer")), inv: InventoryClient = Depends(get_inventory_client)) -> Any:
    return await inv.forward("POST", "/demand-rules/exclusions", json=body, user_id=session.user_id, roles=session.roles)


@router.put("/demand-rules/exclusions/{xid}")
async def toggle_exclusion(xid: int, body: dict[str, Any], if_match: str | None = Header(default=None), session: SessionData = Depends(require_roles("buyer")),
                           inv: InventoryClient = Depends(get_inventory_client)) -> Any:
    return await inv.forward("PUT", f"/demand-rules/exclusions/{xid}", json=body, user_id=session.user_id, roles=session.roles, if_match=if_match)


@router.put("/demand-rules/rules/{rule}")
async def put_rule(request: Request, rule: str, body: dict[str, Any], if_match: str | None = Header(default=None), session: SessionData = Depends(require_roles("buyer")),
                   inv: InventoryClient = Depends(get_inventory_client)) -> Any:
    _need_fresh_mfa(request, session)                          # a censoring rule changes the forecast inputs of many products (owner decision, T063)
    return await inv.forward("PUT", f"/demand-rules/rules/{rule}", json=body, user_id=session.user_id, roles=session.roles, if_match=if_match)


@router.get("/products/{sku}/segment-history")
async def segment_history_by_sku(sku: str, session: SessionData = Depends(require_roles("viewer")), inv: InventoryClient = Depends(get_inventory_client)) -> Any:
    return await inv.forward("GET", f"/products/{sku}/segment-history", user_id=session.user_id, roles=session.roles)


@router.get("/segments/{variant_id}/history")
async def segment_history(variant_id: int, session: SessionData = Depends(require_roles("viewer")), inv: InventoryClient = Depends(get_inventory_client)) -> Any:
    return await inv.forward("GET", f"/segments/{variant_id}/history", user_id=session.user_id, roles=session.roles)


# ---- forecast parameters ---------------------------------------------------------------------------------------------------------

@router.put("/parameters/{key}")
async def put_parameter(request: Request, key: str, body: dict[str, Any], if_match: str | None = Header(default=None), session: SessionData = Depends(require_roles("buyer")),
                        fc: ForecastClient = Depends(get_forecast_client)) -> Any:
    _need_fresh_mfa(request, session)                          # forecast parameters change every forecast (owner decision, T063)
    return await fc.forward("PUT", f"/parameters/{key}", json=body, user_id=session.user_id, roles=session.roles, if_match=if_match)


@router.post("/forecast/runs", status_code=202)
async def request_forecast(session: SessionData = Depends(require_roles("buyer")), fc: ForecastClient = Depends(get_forecast_client)) -> Any:
    return await fc.forward("POST", "/runs", json={}, user_id=session.user_id, roles=session.roles)
