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


def test_seed_container_is_private_encrypted_by_the_service_and_expires():
    """MMI 002 (FR-020): uploaded seed files sit in a private container with a retention rule and one writer identity."""
    seed = re.search(r"resource seed '.*?\n\}", STORAGE, re.S)
    assert seed and "publicAccess: 'None'" in seed.group(0)
    assert 0 < param_default("seedRetentionDays") <= 90
    assert "name: 'expire-seed-files'" in STORAGE and "daysAfterModificationGreaterThan: seedRetentionDays" in STORAGE
    access = re.search(r"resource seedAccess.*?\n\}\]", STORAGE, re.S)
    assert access and "seedPrincipalIds" in access.group(0) and "scope: seed" in access.group(0)


def test_only_forecast_service_is_wired_to_the_seed_container():
    main = (ROOT / "infra/bicep/main.bicep").read_text()
    assert "seedPrincipalIds: [idForecast.properties.principalId]" in main                 # forecast-service alone
    assert "rawWriterPrincipalIds: [idConnector.properties.principalId]" in main           # the connector alone writes raw payloads
    assert "rawReaderPrincipalIds: [idInventory.properties.principalId, idProcurement.properties.principalId]" in main


def test_the_seed_container_is_reachable_by_the_forecast_identity_only_and_its_endpoint_is_exported():
    """T169: forecast-service gets Contributor on the seed container alone; main.bicep exports the endpoint for MMI_SEED_ACCOUNT_URL."""
    access = re.search(r"resource seedAccess.*?\n\}\]", STORAGE, re.S)
    assert access and "scope: seed" in access.group(0) and "blobDataContributor" in access.group(0) and "seedPrincipalIds" in access.group(0)
    assert "output blobEndpoint" in STORAGE
    assert "MMI_SEED_ACCOUNT_URL" in (ROOT / "infra/bicep/main.bicep").read_text()
