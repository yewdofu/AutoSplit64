import copy
import json
import os
import uuid

from as64core.resource_utils import resource_path, user_data_path


_config = {}
_defaults = None
_rollback = None

_CONFIG_VERSION = 2
_CONFIG_FILE_NAME = "config.json"
_LEGACY_CONFIG_FILE_NAME = "config.ini"
_DEFAULTS_FILE_NAME = "defaults.json"
_DEFAULT_PROFILE_ID = "default"

_CAPTURE_PROFILE_KEYS = {
    "game": {
        "override_version", "version", "process_name", "capture_source", "device_index", "device_name",
        "device_resolution", "game_region", "capture_size"
    },
    "model": {"path", "width", "height"},
    "thresholds": {
        "probability_threshold", "confirmation_threshold", "reset_threshold", "white_threshold", "black_threshold",
        "xcam_bg_threshold", "xcam_rg_threshold", "xcam_bg_activation", "xcam_rg_activation",
        "xcam_pixel_threshold"
    },
    "split_final_star": {"stage_lower_bound", "stage_upper_bound", "star_lower_bound", "star_upper_bound"},
    "split_ddd_enter": {"portal_lower_bound", "portal_upper_bound", "hat_lower_bound", "hat_upper_bound"},
    "split_xcam": {"lower_bound", "upper_bound"},
    "advanced": {"reset_frame_one", "reset_frame_two"}
}


def _is_profile_key(section, key):
    return key in _CAPTURE_PROFILE_KEYS.get(section, set())


def _active_profile(data):
    profile_id = data["active_capture_profile"]
    return data["capture_profiles"]["profiles"][profile_id]


def _default_profile():
    return _defaults["capture_profiles"]["profiles"][_DEFAULT_PROFILE_ID]


def _migrate_legacy(data):
    migrated = copy.deepcopy(data)
    profile = copy.deepcopy(_default_profile())

    for section, keys in _CAPTURE_PROFILE_KEYS.items():
        legacy_section = migrated.get(section, {})
        profile_section = profile.setdefault(section, {})
        for key in keys:
            if key in legacy_section:
                profile_section[key] = legacy_section.pop(key)
        if section in migrated and not legacy_section:
            migrated.pop(section)

    migrated["config_version"] = _CONFIG_VERSION
    migrated["active_capture_profile"] = _DEFAULT_PROFILE_ID
    migrated["capture_profiles"] = {
        "profiles": {
            _DEFAULT_PROFILE_ID: profile
        }
    }
    return migrated


def _normalize_config(data):
    version = data.get("config_version")
    if version not in (None, 1, _CONFIG_VERSION):
        raise ValueError(f"Unsupported config version: {version}")

    if "capture_profiles" not in data:
        return _migrate_legacy(data), True

    normalized = False
    if version != _CONFIG_VERSION:
        data["config_version"] = _CONFIG_VERSION
        normalized = True

    profiles = data.get("capture_profiles", {}).get("profiles", {})
    if not profiles:
        data["capture_profiles"] = {"profiles": {_DEFAULT_PROFILE_ID: copy.deepcopy(_default_profile())}}
        data["active_capture_profile"] = _DEFAULT_PROFILE_ID
        return data, True

    active_id = data.get("active_capture_profile")
    if active_id not in profiles:
        data["active_capture_profile"] = next(iter(profiles))
        return data, True

    return data, normalized


def add_section(section):
    global _config
    _config[section] = {}


def remove_section(section):
    global _config
    return _config.pop(section)


def add_key(section, key, value=None):
    set_key(section, key, value)


def remove_key(section, key):
    global _config
    if _is_profile_key(section, key):
        return _active_profile(_config).get(section, {}).pop(key)
    return _config[section].pop(key)


def get(section, key=None, data=None):
    global _config

    if data is None and not _config:
        load_config()
    source = _config if data is None else data

    if key and _is_profile_key(section, key):
        try:
            return _active_profile(source)[section][key]
        except KeyError:
            return get_default(section, key)

    if key:
        try:
            return source[section][key]
        except KeyError:
            return get_default(section, key)

    values = copy.deepcopy(source.get(section, {}))
    try:
        values.update(copy.deepcopy(_active_profile(source).get(section, {})))
    except KeyError:
        pass
    if values:
        return values
    return get_default(section)


def get_default(section, key=None):
    global _defaults

    if not _defaults:
        load_defaults()

    if key and _is_profile_key(section, key):
        return _default_profile().get(section, {}).get(key)

    if key:
        return _defaults.get(section, {}).get(key)

    values = copy.deepcopy(_defaults.get(section, {}))
    values.update(copy.deepcopy(_default_profile().get(section, {})))
    return values or None


def set_key(section, key, value, data=None):
    global _config

    if data is None and not _config:
        load_config()
    target = _config if data is None else data

    if _is_profile_key(section, key):
        profile = _active_profile(target)
        profile.setdefault(section, {})[key] = value
        return

    target.setdefault(section, {})[key] = value


def set_section(section, value):
    global _config
    if section not in _config:
        raise KeyError(section)
    _config[section] = value


def create_rollback():
    global _rollback
    _rollback = copy.deepcopy(_config)


def rollback():
    global _config
    if _rollback is not None:
        _config = copy.deepcopy(_rollback)


def flush_rollback():
    global _rollback
    rollback_data = _rollback
    _rollback = None
    return rollback_data


def load_config():
    global _config
    load_defaults()

    config_path = user_data_path(_CONFIG_FILE_NAME)
    legacy_path = user_data_path(_LEGACY_CONFIG_FILE_NAME)
    migrated = False

    try:
        with open(config_path, encoding="utf-8") as file:
            data = json.load(file)
    except FileNotFoundError:
        try:
            with open(legacy_path, encoding="utf-8") as file:
                data = json.load(file)
            migrated = True
        except FileNotFoundError:
            generate_config()
            return

    _config, normalized = _normalize_config(data)
    if migrated or normalized:
        save_config()


def load_defaults():
    global _defaults
    with open(resource_path(_DEFAULTS_FILE_NAME), encoding="utf-8") as file:
        _defaults = json.load(file)


def save_config():
    config_path = user_data_path(_CONFIG_FILE_NAME)
    temporary_path = config_path + ".tmp"
    with open(temporary_path, "w", encoding="utf-8") as file:
        json.dump(_config, file, indent=4)
        file.write("\n")
    os.replace(temporary_path, config_path)
    flush_rollback()


def generate_config():
    global _config
    load_defaults()
    _config = copy.deepcopy(_defaults)
    save_config()


def copy_config():
    if not _config:
        load_config()
    return copy.deepcopy(_config)


def replace_config(data):
    global _config
    _config = copy.deepcopy(data)


def get_capture_profiles(data=None):
    if data is None and not _config:
        load_config()
    source = _config if data is None else data
    return [(profile_id, profile["name"])
            for profile_id, profile in source["capture_profiles"]["profiles"].items()]


def get_active_capture_profile_id(data=None):
    if data is None and not _config:
        load_config()
    source = _config if data is None else data
    return source["active_capture_profile"]


def get_active_capture_profile_name(data=None):
    if data is None and not _config:
        load_config()
    source = _config if data is None else data
    return _active_profile(source)["name"]


def set_active_capture_profile(profile_id, data=None):
    if data is None and not _config:
        load_config()
    target = _config if data is None else data
    if profile_id not in target["capture_profiles"]["profiles"]:
        raise KeyError(profile_id)
    target["active_capture_profile"] = profile_id


def _validate_profile_name(name, exclude_profile_id=None, data=None):
    source = _config if data is None else data
    normalized_name = name.strip()
    if not normalized_name:
        raise ValueError("Profile name cannot be empty.")
    for profile_id, profile in source["capture_profiles"]["profiles"].items():
        if profile_id != exclude_profile_id and profile["name"].casefold() == normalized_name.casefold():
            raise ValueError("A capture profile with this name already exists.")
    return normalized_name


def create_capture_profile(name, source_profile_id=None, data=None):
    target = _config if data is None else data
    normalized_name = _validate_profile_name(name, data=target)
    profiles = target["capture_profiles"]["profiles"]
    source_id = source_profile_id or get_active_capture_profile_id(target)
    if source_id not in profiles:
        raise KeyError(source_id)

    profile_id = uuid.uuid4().hex
    profile = copy.deepcopy(profiles[source_id])
    profile["name"] = normalized_name
    profiles[profile_id] = profile
    return profile_id


def rename_capture_profile(profile_id, name, data=None):
    target = _config if data is None else data
    normalized_name = _validate_profile_name(name, exclude_profile_id=profile_id, data=target)
    target["capture_profiles"]["profiles"][profile_id]["name"] = normalized_name


def delete_capture_profile(profile_id, data=None):
    target = _config if data is None else data
    profiles = target["capture_profiles"]["profiles"]
    if len(profiles) <= 1:
        raise ValueError("At least one capture profile is required.")
    if profile_id not in profiles:
        raise KeyError(profile_id)

    profiles.pop(profile_id)
    if get_active_capture_profile_id(target) == profile_id:
        target["active_capture_profile"] = next(iter(profiles))
    return get_active_capture_profile_id(target)
