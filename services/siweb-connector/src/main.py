"""siweb-connector service entrypoint (skeleton: health endpoints and authentication wiring)."""

from local_sync import register as register_local_sync
from mmi_common.service import create_service_app

app = create_service_app("siweb-connector")
register_local_sync(app)          # mounted only for the local export loader (MMI_LOCAL_LOADER=1, never in prod/staging)
