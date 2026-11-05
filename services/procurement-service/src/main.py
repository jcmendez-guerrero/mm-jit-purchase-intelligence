"""procurement-service entrypoint: health/auth wiring, the cost, terms and proposal APIs, and production dependencies.

The inputs provider, user directory and blob writer are created at startup from the environment (nothing is created at
import, so tests and tools can import this module freely). Without configuration the proposal endpoints answer 503.
"""

import os
from decimal import Decimal
from pathlib import Path

from api.costs import build_router, get_engine
from api.proposals import build_router as build_proposal_router
from mmi_common.service import create_service_app
from mmi_common.servicetoken import service_token

app = create_service_app("procurement-service")
app.include_router(build_router(app))
app.include_router(build_proposal_router(app))


def configure() -> None:
    if not os.environ.get("MMI_DATABASE_URL"):
        return
    from proposals.inputs import HttpJsonSource, InputsProvider
    from users.directory import DbUserDirectory

    class FileWriter:
        def __init__(self, root: Path) -> None:
            self.root = root

        def put(self, name: str, data: bytes) -> str:
            p = (self.root / name).resolve()
            if self.root.resolve() not in p.parents:
                raise ValueError("blob name escapes the store")
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(data)
            return p.as_uri()

    app.state.user_directory = DbUserDirectory(get_engine())
    app.state.blob_writer = FileWriter(Path(os.environ.get("MMI_BLOB_ROOT", "/tmp/mmi-procurement")))  # noqa: S108 - local default only
    if os.environ.get("MMI_INVENTORY_URL") and os.environ.get("MMI_FORECAST_URL"):
        static = os.environ.get("MMI_UPSTREAM_TOKEN")

        def token_for(audience: str):  # type: ignore[no-untyped-def]
            return static or (lambda: service_token(audience, "svc-procurement", ["viewer"]))

        budget = os.environ.get("MMI_WEEKLY_BUDGET")
        app.state.inputs_provider = InputsProvider(
            HttpJsonSource(os.environ["MMI_INVENTORY_URL"].rstrip("/") + "/export/stock", token_for("api://mmi-inventory-service")),
            HttpJsonSource(os.environ["MMI_FORECAST_URL"].rstrip("/") + "/forecasts/latest", token_for("api://mmi-forecast-service")), Decimal(budget) if budget else None)


app.router.on_startup.append(configure)
