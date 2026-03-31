from types import SimpleNamespace

from custom_components.huawei_charger.const import DOMAIN
from custom_components.huawei_charger.services import (
    _coerce_service_value,
    _get_coordinators,
    _resolve_single_coordinator,
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

    def set_config_value(self, param_id, value):
        self.calls.append(("set_config_value", param_id, value))
        return True

    def start_charge(self, *, gun_number=1, account_id=None):
        self.calls.append(("start_charge", gun_number, account_id))
        return True

    def stop_charge(self, *, gun_number=1, order_number=None, serial_number=None):
        self.calls.append(("stop_charge", gun_number, order_number, serial_number))
        return True


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


def test_resolve_single_coordinator_returns_matching_entry():
    coordinator = DummyCoordinator(entry_id="entry-1")
    hass = SimpleNamespace(data={DOMAIN: {"entry-1": coordinator}})
    call = SimpleNamespace(data={"entry_id": "entry-1"})

    assert _resolve_single_coordinator(hass, call, "start_charge") is coordinator


def test_coerce_service_value_parses_common_scalars():
    assert _coerce_service_value("true") is True
    assert _coerce_service_value("false") is False
    assert _coerce_service_value("42") == 42
    assert _coerce_service_value("4.2") == 4.2
    assert _coerce_service_value("start") == "start"
