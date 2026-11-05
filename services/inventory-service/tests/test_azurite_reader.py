"""T153: inventory-service reads the connector's payloads from blob storage (Azurite). Needs Docker and RUN_AZURITE=1."""

import pytest
from azurite_fixture import available, azurite
from projections.blob import AzureBlobReader

pytestmark = pytest.mark.skipif(not available(), reason="needs Docker and RUN_AZURITE=1")


def test_reader_fetches_the_payload_by_the_uri_the_connector_published():
    from azure.storage.blob import ContainerClient

    with azurite() as conn:
        cc = ContainerClient.from_connection_string(conn, "raw")
        cc.create_container()
        blob = cc.get_blob_client("raw/movements/2026/11/05/run-1.json")
        blob.upload_blob(b'{"kind":"movements"}')
        assert AzureBlobReader.from_connection_string(conn, "raw").get(blob.url) == b'{"kind":"movements"}'
