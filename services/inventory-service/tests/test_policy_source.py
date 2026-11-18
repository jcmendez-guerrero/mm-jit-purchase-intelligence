"""T010a: the classification configuration version is stable for the same values and changes when any threshold changes."""

from classification.policy_source import PREFIX, current_config, version_id
from classification.segments import ClassificationConfig


def test_current_config_is_the_defaults_with_a_stable_version():
    cfg, v1 = current_config()
    _, v2 = current_config()
    assert cfg == ClassificationConfig() and v1 == v2 and v1.startswith(PREFIX)


def test_version_fits_the_36_character_column():
    assert len(current_config()[1]) <= 36


def test_any_threshold_change_gives_a_new_version():
    base = version_id(ClassificationConfig())
    assert version_id(ClassificationConfig(adi_cutoff=1.5)) != base
    assert version_id(ClassificationConfig(min_nonzero_blocks=10)) != base
