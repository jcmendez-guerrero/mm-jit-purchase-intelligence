from upload_settings import MIB, load_limits


def test_default_limit_is_five_mib(monkeypatch):
    monkeypatch.delenv("MMI_UPLOAD_MAX_BYTES", raising=False)
    assert load_limits().max_bytes == 5 * MIB


def test_env_overrides_but_is_capped(monkeypatch):
    monkeypatch.setenv("MMI_UPLOAD_MAX_BYTES", str(1 * MIB))
    assert load_limits().max_bytes == MIB
    monkeypatch.setenv("MMI_UPLOAD_MAX_BYTES", str(900 * MIB))
    assert load_limits().max_bytes == 25 * MIB


def test_bad_values_fall_back_to_default(monkeypatch):
    for bad in ("abc", "-1", "0", ""):
        monkeypatch.setenv("MMI_UPLOAD_MAX_BYTES", bad)
        assert load_limits().max_bytes == 5 * MIB


def test_only_csv_and_xlsx_are_allowed():
    assert load_limits().allowed_extensions == (".csv", ".xlsx")
