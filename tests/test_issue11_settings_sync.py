"""
Issue #11: adding a settings page required updating menu_list,
stacked_widget, show(), and apply_clicked() in four separate places -
forgetting one (e.g. apply_clicked) left a page whose Apply button silently
did not save. Each menu's load_preferences/update_preferences also
repeated the same config.get/set_key call twice per field (once to load,
once to save) with no link between the two.

Verifies SettingsDialog drives registration from a single `pages` list, and
that BaseMenu.FIELDS keeps a field's load and save sides from drifting
apart - including GeneralMenu's override-version combo, which needs extra
logic beyond a plain field mapping.

Only mutates config in memory (never calls config.save_config()), and
restores the original in-memory config after each test that changes it, so
this never touches the real config.json on disk.
"""
import copy

import pytest

from as64core import config


@pytest.fixture(autouse=True)
def restore_config():
    """Every test starts from, and is left with, the config.json snapshot taken at session start - in memory only."""
    if not config._config:
        config.load_config()
    snapshot = copy.deepcopy(config._config)
    yield
    config.replace_config(snapshot)


def test_settings_dialog_pages_drive_registration(qapp):
    from as64gui.dialogs.settings_dialog import SettingsDialog

    dlg = SettingsDialog()
    labels = [name for name, _ in dlg.pages]
    assert labels == ["General", "Connection", "Thresholds", "Colour Thresholds", "Error Correction", "Advanced"]
    assert [dlg.menu_list.item(i).text() for i in range(dlg.menu_list.count())] == labels
    assert dlg.stacked_widget.count() == len(dlg.pages)


def test_load_then_update_with_no_edits_leaves_config_unchanged(qapp):
    from as64gui.dialogs.settings_dialog import SettingsDialog

    before = copy.deepcopy(config.copy_config())
    dlg = SettingsDialog()
    for _, menu in dlg.pages:
        menu.load_preferences()
    for _, menu in dlg.pages:
        menu.update_preferences()
    assert config.copy_config() == before


def test_connection_menu_simple_fields_round_trip(qapp):
    from as64gui.dialogs.settings_dialog import ConnectionMenu

    menu = ConnectionMenu()
    menu.load_preferences()
    assert menu.host_le.text() == str(config.get("connection", "ls_host"))
    assert menu.port_le.text() == str(config.get("connection", "ls_port"))

    menu.host_le.setText("changed-host")
    menu.port_le.setText("12345")
    menu.update_preferences()

    assert config.get("connection", "ls_host") == "changed-host"
    assert config.get("connection", "ls_port") == 12345


def test_thresholds_menu_field_definitions_cover_every_widget(qapp):
    from as64gui.dialogs.settings_dialog import ThresholdsMenu

    menu = ThresholdsMenu()
    widgets_with_fields = {widget for widget, *_ in menu.FIELDS}
    for widget in (menu.prob_le, menu.reset_le, menu.confirmation_le, menu.black_le,
                   menu.white_le, menu.xcam_bg_le, menu.xcam_rg_le,
                   menu.xcam_bg_activation_le, menu.xcam_rg_activation_le,
                   menu.xcam_pixel_le, menu.undo_le):
        assert widget in widgets_with_fields


def test_general_menu_override_version_extra_logic_still_works(qapp):
    from as64gui.dialogs.settings_dialog import GeneralMenu

    menu = GeneralMenu()
    menu.load_preferences()

    menu.override_ver_cb.setChecked(True)
    menu.override_ver_combo.setCurrentIndex(1)  # "US"
    menu.on_top_cb.setChecked(not menu.on_top_cb.isChecked())
    expected_on_top = menu.on_top_cb.isChecked()

    menu.update_preferences()

    assert config.get("game", "override_version") is True
    assert config.get("game", "version") == "US"
    # The plain FIELDS-driven checkbox must still be saved alongside the
    # hand-written override-version logic.
    assert config.get("general", "on_top") == expected_on_top


def test_colour_thresholds_menu_widgets_driven_by_a_single_list(qapp):
    from as64gui.dialogs.settings_dialog import ColourThresholdsMenu

    menu = ColourThresholdsMenu()
    assert len(menu.COLOUR_WIDGETS) == 10
    assert menu.portal_lower_bound in menu.COLOUR_WIDGETS
    assert menu.xcam_upper_bound in menu.COLOUR_WIDGETS
