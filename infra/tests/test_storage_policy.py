"""T154: raw payloads are immutable until retention ends, then deleted; only the connector writes, only readers read."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STORAGE = (ROOT / "infra/bicep/modules/storage.bicep").read_text()


def param_default(name: str) -> int:
    m = re.search(rf"param {name} int = (\d+)", STORAGE)
    assert m, name
    return int(m.group(1))


def test_the_raw_container_has_a_time_based_immutability_policy():
    assert "containers/immutabilityPolicies" in STORAGE and "immutabilityPeriodSinceCreationInDays: rawImmutableDays" in STORAGE
    assert "allowProtectedAppendWrites: false" in STORAGE


def test_immutability_ends_before_the_retention_so_expired_payloads_can_be_deleted():
    assert 0 < param_default("rawImmutableDays") < param_default("rawRetentionDays")
    assert "daysAfterModificationGreaterThan: rawRetentionDays" in STORAGE


def test_access_is_least_privilege():
    assert "allowBlobPublicAccess: false" in STORAGE and "allowSharedKeyAccess: false" in STORAGE
    roles = set(re.findall(r"= '([0-9a-f-]{36})'\s+//\s+(.+)", STORAGE))
    assert {name.strip() for _, name in roles} == {"Storage Blob Data Contributor", "Storage Blob Data Reader"}
    assert "rawWriterPrincipalIds" in STORAGE and "rawReaderPrincipalIds" in STORAGE
    writers = re.search(r"resource rawWriters.*?\n\}\]", STORAGE, re.S)
    readers = re.search(r"resource rawReaders.*?\n\}\]", STORAGE, re.S)
    assert writers and "blobDataContributor" in writers.group(0) and readers and "blobDataReader" in readers.group(0) and "Contributor" not in readers.group(0)
