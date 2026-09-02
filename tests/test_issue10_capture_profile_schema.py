"""
Issue #10: which config keys are capture-profile-scoped vs. global was
defined twice - once as a hardcoded _CAPTURE_PROFILE_KEYS dict in config.py,
and once implicitly by which keys the default profile in defaults.json
actually contains. Adding a profile key to one without the other silently
changed where it got read from/written to.

Verifies _profile_schema() derives {section: {key, ...}} straight from
defaults.json's default profile (the single source of truth now), and that
_migrate_legacy correctly splits legacy flat sections into profile-scoped
vs. global data using that same schema.
"""
import copy

from as64core import config


def setup_module(module):
    # Only reads defaults.json - never touches the user's real config.json.
    config.load_defaults()


def test_profile_schema_matches_known_sections():
    schema = config._profile_schema()
    assert set(schema.keys()) == {
        "game", "model", "thresholds", "split_final_star",
        "split_ddd_enter", "split_xcam", "advanced",
    }
    # "name" is a profile field but not a config section - must be excluded.
    assert "name" not in schema


def test_profile_keys_are_correctly_scoped():
    assert config._is_profile_key("game", "device_resolution")
    assert config._is_profile_key("thresholds", "probability_threshold")
    assert config._is_profile_key("advanced", "reset_frame_one")

    # These sections also carry global (non-profile) keys of the same name -
    # the whole point of issue #10 is telling these apart correctly.
    assert not config._is_profile_key("thresholds", "undo_threshold")
    assert not config._is_profile_key("advanced", "restart_split_delay")
    assert not config._is_profile_key("connection", "ls_host")


def test_migrate_legacy_splits_profile_and_global_keys_by_schema():
    legacy_data = {
        "game": {"capture_source": "window", "device_resolution": [1920, 1080]},
        "thresholds": {"probability_threshold": 0.75, "undo_threshold": 9.9},
        "advanced": {"reset_frame_one": "custom_one.jpg", "restart_split_delay": 2.5},
        "connection": {"ls_host": "myhost"},
    }

    migrated = config._migrate_legacy(copy.deepcopy(legacy_data))
    profile = migrated["capture_profiles"]["profiles"]["default"]

    assert profile["game"]["capture_source"] == "window"
    assert profile["game"]["device_resolution"] == [1920, 1080]
    assert profile["thresholds"]["probability_threshold"] == 0.75
    assert profile["advanced"]["reset_frame_one"] == "custom_one.jpg"

    # Global keys stay at the top level; profile keys are removed from there.
    assert migrated["thresholds"] == {"undo_threshold": 9.9}
    assert migrated["advanced"] == {"restart_split_delay": 2.5}
    assert migrated["connection"] == {"ls_host": "myhost"}


def test_adding_a_profile_key_only_requires_editing_defaults_json():
    # Simulate a new profile-scoped key that only exists in defaults.json's
    # profile (no code change needed) - _is_profile_key must pick it up.
    default_profile = config._default_profile()
    default_profile.setdefault("game", {})["_test_new_key"] = "value"
    try:
        assert config._is_profile_key("game", "_test_new_key")
    finally:
        del default_profile["game"]["_test_new_key"]
