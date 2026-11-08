"""T098 (FR-040, R1a): a locally assigned id (>= 9,000,000) is never put into a request to the real ERP; the mock may receive them."""

import pytest
from allowlist.allowlist import LOCAL_ID_FLOOR, Allowlist, AllowlistViolation

REAL = "siweb.example.test"
PATHS = ["/api/public/inventory/products/{id}", "/api/public/inventory/products/{id}/suppliers", "/api/public/inventory/variants/{id}",
         "/api/public/inventory/variants/{id}/stock", "/api/public/inventory/variants/{id}/lots", "/api/public/inventory/variants/{id}/movements",
         "/api/public/purchases/{id}"]


@pytest.mark.parametrize("path", PATHS)
def test_the_real_erp_never_receives_a_local_id(path):
    with pytest.raises(AllowlistViolation) as e:
        Allowlist(REAL).check("GET", f"https://{REAL}{path.format(id=LOCAL_ID_FLOOR)}")
    assert e.value.reason == "local_id_refused"


@pytest.mark.parametrize("path", PATHS)
def test_ids_just_below_the_floor_are_ordinary_erp_ids(path):
    Allowlist(REAL).check("GET", f"https://{REAL}{path.format(id=LOCAL_ID_FLOOR - 1)}")


@pytest.mark.parametrize("host", ["siweb-mock", "localhost", "127.0.0.1"])
def test_the_local_mock_may_receive_them(host):
    Allowlist(host, allow_http=True).check("GET", f"http://{host}:8089/api/public/inventory/variants/{LOCAL_ID_FLOOR + 5}/lots")


def test_the_query_string_is_checked_too():
    with pytest.raises(AllowlistViolation) as e:
        Allowlist(REAL).check("GET", f"https://{REAL}/api/public/inventory/movements?variant_id={LOCAL_ID_FLOOR + 1}")
    assert e.value.reason == "local_id_refused"


def test_the_refusal_is_counted_and_never_echoes_the_query():
    a = Allowlist(REAL)
    with pytest.raises(AllowlistViolation):
        a.check("GET", f"https://{REAL}/api/public/inventory/movements?variant_id={LOCAL_ID_FLOOR + 1}&secret=x")
    assert a.refusals[0][0] == "local_id_refused" and "secret" not in a.refusals[0][2]
