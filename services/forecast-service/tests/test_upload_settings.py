from upload_settings import MIB, load_limits


def test_defaults(monkeypatch):
    monkeypatch.delenv("MMI_UPLOAD_MAX_BYTES", raising=False)
    lim = load_limits()
    assert (lim.max_bytes, lim.max_rows, lim.max_columns, lim.max_sheets) == (5 * MIB, 50_000, 30, 5)
    assert lim.max_decompressed_bytes >= 10 * lim.max_bytes


def test_env_limit_is_capped(monkeypatch):
    monkeypatch.setenv("MMI_UPLOAD_MAX_BYTES", str(999 * MIB))
    assert load_limits().max_bytes == 25 * MIB
