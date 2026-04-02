from types import SimpleNamespace

from custom_components.huawei_charger.const import DOMAIN
from custom_components.huawei_charger.services import (
    _get_coordinators,
    _refresh_config_signals,
    build_config_signal_dump,
)


class DummyCoordinator:
    def __init__(self, entry_id="entry-1", wallbox_dn="NE=1", wallbox_dn_id="wallbox-1"):
        self.entry = SimpleNamespace(entry_id=entry_id)
        self.auth_host = "uni005eu5.fusionsolar.huawei.com"
        self.wallbox_dn = wallbox_dn
        self.wallbox_dn_id = wallbox_dn_id
        self.config_signal_details = {
            "20001": {
                "id": "20001",
                "name": "Dynamic Power Limit",
                "value": 4.2,
                "writable": True,
                "min": 1.4,
                "max": 22,
            },
            "30001": {
                "id": "30001",
                "name": "Working Mode",
                "value": "Scheduled Charge",
                "writable": True,
                "options": [
                    "Normal Charge",
                    "Scheduled Charge",
                    "PV Power Preferred",
                ],
            },
            "20034": {
                "id": "20034",
                "name": "Authentication Password",
                "value": "secret",
            },
        }
        self.calls = []

    def _ensure_device_context(self):
        self.calls.append("ensure")

    def fetch_wallbox_info(self):
        self.calls.append("fetch_info")

    def fetch_wallbox_config_probe(self):
        self.calls.append("fetch_probe")

    def _update_register_debug_state(self):
        self.calls.append("update_debug")


def test_build_config_signal_dump_highlights_candidates_and_masks_sensitive():
    coordinator = DummyCoordinator()

    dump = build_config_signal_dump(coordinator)

    assert "session_control_candidates:" in dump
    assert "id=30001" in dump
    assert "Working Mode" in dump
    assert "keywords=mode,prefer,schedule,scheduled,work" in dump
    assert "id=20034" not in dump
    assert "Authentication Password" not in dump


def test_refresh_config_signals_uses_config_probe_when_wallbox_is_known():
    coordinator = DummyCoordinator()

    _refresh_config_signals(coordinator)

    assert coordinator.calls == ["ensure", "fetch_probe", "update_debug"]


def test_refresh_config_signals_fetches_wallbox_info_when_wallbox_is_missing():
    coordinator = DummyCoordinator(wallbox_dn=None, wallbox_dn_id=None)

    _refresh_config_signals(coordinator)

    assert coordinator.calls == ["ensure", "fetch_info"]


def test_get_coordinators_filters_internal_keys_and_entry_id():
    first = DummyCoordinator(entry_id="entry-1")
    second = DummyCoordinator(entry_id="entry-2")
    hass = SimpleNamespace(
        data={
            DOMAIN: {
                "entry-1": first,
                "entry-2": second,
                "_cards_registered": True,
            }
        }
    )

    assert _get_coordinators(hass) == [first, second]
    assert _get_coordinators(hass, entry_id="entry-2") == [second]
