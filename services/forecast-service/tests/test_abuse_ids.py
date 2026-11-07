"""T156 (forecast part): identifiers are never trusted as paths, and an unknown or foreign id reveals nothing."""

import pytest
from seeds.files import LocalSeedStore
from test_imports_api import api, h  # noqa: F401  (the same app fixture and headers)


def test_the_file_store_refuses_names_and_references_outside_its_root(tmp_path):
    store = LocalSeedStore(tmp_path / "seeds")
    (tmp_path / "secret.txt").write_text("not for the store")
    with pytest.raises(ValueError):
        store.put("../secret.txt", b"x")
    with pytest.raises(ValueError):
        store.put("/etc/passwd", b"x")
    with pytest.raises(ValueError):
        store.get((tmp_path / "secret.txt").as_uri())
    ref = store.put("d1/original.csv", b"a;b")
    assert store.get(ref) == b"a;b"


@pytest.mark.parametrize("bad_id", ["..%2F..%2Fetc%2Fpasswd", "nope", "0" * 36, "%00", "a" * 300])
def test_unknown_dataset_ids_get_a_plain_refusal_on_every_dataset_route(api, bad_id):  # noqa: F811
    for method, tail in (("post", "validate"), ("get", "quarantine"), ("post", "dry-run"), ("post", "activate"), ("post", "reject")):
        res = getattr(api, method)(f"/imports/{bad_id}/{tail}", headers=h("buyer"))
        detail = res.json().get("detail")
        assert res.status_code in (404, 422), (tail, res.status_code)
        assert detail in ("import_unknown_dataset", "Not Found") or isinstance(detail, list), (tail, detail)      # a code, or the router not matching a mangled path
        assert "Traceback" not in res.text and "/etc/" not in res.text
