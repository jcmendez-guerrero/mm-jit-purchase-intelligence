"""Job wiring: configuration, token handling and the writer's separation from the reader."""

import job
import pytest
from sqlalchemy import create_engine


def env(monkeypatch, **extra):
    base = {"MMI_DATABASE_URL": "sqlite://", "MMI_SIWEB_BASE_URL": "https://siweb.example.test", "MMI_PROCUREMENT_URL": "http://proc.test",
            "MMI_PROCUREMENT_TOKEN": "svc", "MMI_SIWEB_WRITER_TOKEN": "writer-secret"}
    for k, v in {**base, **extra}.items():
        monkeypatch.setenv(k, v)


def test_processor_is_built_from_the_environment_with_the_host_allowlist(monkeypatch, tmp_path):
    env(monkeypatch, MMI_BLOB_ROOT=str(tmp_path))
    proc, allowlist = job.build_processor()
    assert allowlist.host == "siweb.example.test" and not allowlist.allow_http
    assert "writer-secret" not in repr(proc.siweb.tokens) and "svc" not in repr(proc.procurement)
    assert proc.max_attempts == 5 and create_engine("sqlite://")


def test_plain_http_is_refused_unless_explicitly_enabled_for_the_local_mock(monkeypatch, tmp_path):
    env(monkeypatch, MMI_SIWEB_BASE_URL="http://mock.test", MMI_BLOB_ROOT=str(tmp_path))
    _, allowlist = job.build_processor()
    assert not allowlist.allow_http
    monkeypatch.setenv("MMI_ALLOW_HTTP", "1")
    assert job.build_processor()[1].allow_http


def test_the_job_fails_visibly_without_configuration(monkeypatch):
    monkeypatch.delenv("MMI_DATABASE_URL", raising=False)
    assert job.main() == 1


def test_blob_names_cannot_escape_the_store(tmp_path):
    with pytest.raises(ValueError):
        job.FileBlobs(tmp_path).put("../outside.json", b"x")
