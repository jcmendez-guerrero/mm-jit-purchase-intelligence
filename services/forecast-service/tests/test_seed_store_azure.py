"""T169 (FR-020, ADR-020): seed originals go to the private container through the same interface as the local store.

The unit tests use an in-memory stand-in for the Azure container client; the Azurite test runs only with RUN_AZURITE=1 and Docker.
"""

import pytest
from azurite_fixture import available, azurite
from seeds.files import LocalSeedStore
from seeds.store import AzureSeedStore, make_seed_store


class Blob:
    def __init__(self, store, name):
        self.store, self.name, self.url = store, name, f"https://acct.blob.core.windows.net/seed-quarantine/{name}"

    def upload_blob(self, data, overwrite=False, **_kw):
        if not overwrite and self.name in self.store:
            raise RuntimeError("exists")
        self.store[self.name] = data

    def download_blob(self):
        data = self.store[self.name]

        class R:
            def readall(self):
                return data

        return R()


class Container:
    container_name = "seed-quarantine"

    def __init__(self):
        self.blobs = {}

    def get_blob_client(self, name):
        return Blob(self.blobs, name)


def test_put_returns_a_reference_that_get_reads_back():
    c = Container()
    store = AzureSeedStore(c)
    ref = store.put("d1/original.csv", b"a;b")
    assert ref.endswith("/seed-quarantine/d1/original.csv") and store.get(ref) == b"a;b"
    assert c.blobs == {"d1/original.csv": b"a;b"}


@pytest.mark.parametrize("bad", ["../x", "/etc/passwd", "a/../../b", "", "a\\b"])
def test_names_that_escape_the_container_are_refused(bad):
    with pytest.raises(ValueError):
        AzureSeedStore(Container()).put(bad, b"x")


def test_a_reference_from_another_container_is_refused():
    with pytest.raises(ValueError):
        AzureSeedStore(Container()).get("https://acct.blob.core.windows.net/raw-payloads/x.csv")


def test_the_factory_picks_the_store_from_configuration(tmp_path, monkeypatch):
    for k in ("MMI_SEED_ACCOUNT_URL", "MMI_SEED_CONNECTION", "MMI_SEED_ROOT"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("MMI_SEED_ROOT", str(tmp_path))
    assert isinstance(make_seed_store(), LocalSeedStore)
    monkeypatch.setenv("MMI_ENV", "prod")
    with pytest.raises(RuntimeError):                       # production never falls back to a local folder
        make_seed_store()


@pytest.mark.skipif(not available(), reason="needs Docker and RUN_AZURITE=1")
def test_round_trip_on_azurite():
    with azurite() as conn:
        store = AzureSeedStore.from_connection_string(conn, "seed-quarantine")
        ref = store.put("d1/original.csv", b"x;y")
        assert store.get(ref) == b"x;y"
