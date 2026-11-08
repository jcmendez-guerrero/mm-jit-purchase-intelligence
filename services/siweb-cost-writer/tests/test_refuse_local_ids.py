"""T098 (FR-040): the writer never sends a locally assigned id (>= 9,000,000) anywhere, not even to the mock."""

import httpx
import pytest
from writer.allowlist import LOCAL_ID_FLOOR, AllowlistViolation, WriterAllowlist
from writer.client import SiwebWriterClient, StaticToken

HOST = "siweb.example.test"


def client(calls):
    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, json={"data": []})

    return SiwebWriterClient(http=httpx.Client(transport=httpx.MockTransport(handler)), base_url=f"https://{HOST}", allowlist=WriterAllowlist(HOST), tokens=StaticToken("t"))


@pytest.mark.parametrize(("product", "contact"), [(LOCAL_ID_FLOOR, 7), (5, LOCAL_ID_FLOOR), (LOCAL_ID_FLOOR + 10, LOCAL_ID_FLOOR + 10)])
def test_a_put_with_a_local_id_is_refused_before_any_request(product, contact):
    calls: list = []
    with pytest.raises(AllowlistViolation) as e:
        client(calls).put_supplier(product, contact, {"purchase_cost_cents": 100})
    assert e.value.reason == "local_id_refused" and calls == []


def test_a_supplier_list_read_for_a_local_product_is_refused_too():
    calls: list = []
    with pytest.raises(AllowlistViolation):
        client(calls).get_supplier(LOCAL_ID_FLOOR, 7)
    assert calls == []


def test_ordinary_erp_ids_still_work():
    calls: list = []
    c = client(calls)
    c.get_supplier(LOCAL_ID_FLOOR - 1, 123456)
    assert len(calls) == 1


def test_the_allowlist_itself_refuses_regardless_of_the_host():
    for host in ("siweb-mock", "localhost", HOST):
        with pytest.raises(AllowlistViolation):
            WriterAllowlist(host, allow_http=True).check("PUT", f"http://{host}/api/public/inventory/products/{LOCAL_ID_FLOOR}/suppliers/7")
