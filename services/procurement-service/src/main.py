"""procurement-service entrypoint: health/auth wiring, the cost, terms and proposal APIs, and production dependencies.

The inputs provider, user directory and blob writer are created at startup from the environment (nothing is created at
import, so tests and tools can import this module freely). Without configuration the proposal endpoints answer 503.
"""

import os
from decimal import Decimal
from pathlib import Path

from api.costs import build_router, get_engine
from api.policies import build_router as build_policy_router
from api.proposals import build_router as build_proposal_router
from api.scenarios import build_router as build_scenario_router
from api.summary import build_router as build_summary_router
from mmi_common.service import create_service_app
from mmi_common.servicetoken import service_token

app = create_service_app("procurement-service")
app.include_router(build_router(app))
app.include_router(build_proposal_router(app))
app.include_router(build_policy_router(app))
app.include_router(build_summary_router(app))
app.include_router(build_scenario_router(app))


def configure() -> None:
    if not os.environ.get("MMI_DATABASE_URL"):
        return
    from proposals.blob_store import FileWriter
    from proposals.inputs import HttpJsonSource, InputsProvider
    from users.directory import DbUserDirectory

    app.state.user_directory = DbUserDirectory(get_engine())
    app.state.blob_writer = FileWriter(Path(os.environ.get("MMI_BLOB_ROOT", "/tmp/mmi-procurement")))  # noqa: S108 - local default only
    if os.environ.get("MMI_INVENTORY_URL"):
        from costs.lot_lookup import HttpLotsSource

        lot_token = os.environ.get("MMI_UPSTREAM_TOKEN") or (lambda: service_token("api://mmi-inventory-service", "svc-procurement", ["viewer"]))
        app.state.lots_source = HttpLotsSource(os.environ["MMI_INVENTORY_URL"], lot_token)
        from costs.pvp import HttpPvpSource

        app.state.pvp_source = HttpPvpSource(os.environ["MMI_INVENTORY_URL"], lot_token)
    if os.environ.get("MMI_INVENTORY_URL") and os.environ.get("MMI_FORECAST_URL"):
        static = os.environ.get("MMI_UPSTREAM_TOKEN")

        def token_for(audience: str):  # type: ignore[no-untyped-def]
            return static or (lambda: service_token(audience, "svc-procurement", ["viewer"]))

        budget = os.environ.get("MMI_WEEKLY_BUDGET")
        app.state.inputs_provider = InputsProvider(
            HttpJsonSource(os.environ["MMI_INVENTORY_URL"].rstrip("/") + "/export/stock", token_for("api://mmi-inventory-service")),
            HttpJsonSource(os.environ["MMI_FORECAST_URL"].rstrip("/") + "/forecasts/latest", token_for("api://mmi-forecast-service")), Decimal(budget) if budget else None)


app.router.on_startup.append(configure)
