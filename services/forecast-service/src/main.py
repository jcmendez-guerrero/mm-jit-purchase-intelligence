"""forecast-service service entrypoint (skeleton: health endpoints and authentication wiring)."""

from mmi_common.service import create_service_app

app = create_service_app("forecast-service")
