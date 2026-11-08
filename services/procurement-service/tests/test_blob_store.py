import pytest
from proposals.blob_store import FileWriter


def test_a_blob_is_written_inside_the_store(tmp_path):
    uri = FileWriter(tmp_path).put("events/2026/a.json", b"{}")
    assert (tmp_path / "events/2026/a.json").read_bytes() == b"{}" and uri.startswith("file://")


@pytest.mark.parametrize("name", ["../outside.json", "events/../../outside.json", "/etc/outside.json", ""])
def test_a_name_that_leaves_the_store_is_refused(tmp_path, name):
    with pytest.raises(ValueError):
        FileWriter(tmp_path / "store").put(name, b"x")
    assert not (tmp_path / "outside.json").exists()
