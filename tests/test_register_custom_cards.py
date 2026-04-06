import asyncio
import importlib
import logging
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, call

huawei_init = importlib.import_module("custom_components.huawei_charger.__init__")


class FakeConfig:
    def __init__(self, base_path: Path):
        self._base_path = base_path

    def path(self, relative: str) -> str:
        return str(self._base_path / relative)


class FakeHass:
    def __init__(self, base_path: Path, resources=None):
        self.config = FakeConfig(base_path)
        self.data = {}
        if resources is not None:
            self.data["lovelace"] = {"resources": resources}

    async def async_add_executor_job(self, func, *args, **kwargs):
        return func(*args, **kwargs)


class FakeResources:
    def __init__(self, items=None):
        self._items = list(items or [])
        self.created = []

    async def async_get_info(self):
        return {"resources": len(self._items)}

    def async_items(self):
        return list(self._items)

    async def async_create_item(self, item):
        self._items.append(item)
        self.created.append(item)
        return item


class FakeResourceItem:
    def __init__(self, url: str):
        self.url = url


class FakeLovelaceData:
    def __init__(self, resources):
        self.resources = resources


def test_register_custom_cards_copies_once(tmp_path, monkeypatch):
    resources = FakeResources()
    hass = FakeHass(tmp_path, resources=resources)
    added_urls = []

    def record_js_url(hass_arg, url):
        added_urls.append(url)

    monkeypatch.setattr(huawei_init, "add_extra_js_url", record_js_url)

    asyncio.run(huawei_init.register_custom_cards(hass))

    target_dir = tmp_path / "www" / "community" / "huawei_charger"
    for card_file in huawei_init.CUSTOM_CARDS:
        assert (target_dir / card_file).exists()

    assert added_urls == [
        f"/local/community/huawei_charger/{card}" for card in huawei_init.CUSTOM_CARDS
    ]
    assert resources.created == [
        {"url": f"/local/community/huawei_charger/{card}", "res_type": "module"}
        for card in huawei_init.CUSTOM_CARDS
    ]
    assert hass.data[huawei_init.DOMAIN]["_cards_registered"] is True

    asyncio.run(huawei_init.register_custom_cards(hass))
    assert added_urls == [
        f"/local/community/huawei_charger/{card}" for card in huawei_init.CUSTOM_CARDS
    ]


def test_register_custom_cards_handles_missing(tmp_path, monkeypatch, caplog):
    resources = FakeResources()
    hass = FakeHass(tmp_path, resources=resources)
    added_urls = []
    caplog.set_level(logging.INFO)

    monkeypatch.setattr(huawei_init, "add_extra_js_url", lambda hass_arg, url: added_urls.append(url))
    monkeypatch.setattr(
        huawei_init,
        "CUSTOM_CARDS",
        list(huawei_init.CUSTOM_CARDS) + ["missing-card.js"],
    )

    asyncio.run(huawei_init.register_custom_cards(hass))

    target_dir = tmp_path / "www" / "community" / "huawei_charger"
    for card_file in huawei_init.CUSTOM_CARDS:
        if card_file == "missing-card.js":
            assert not (target_dir / card_file).exists()
        else:
            assert (target_dir / card_file).exists()

    assert "/local/community/huawei_charger/missing-card.js" not in added_urls
    assert "/local/community/huawei_charger/missing-card.js" not in {
        item["url"] for item in resources.created
    }
    assert any("Custom card file not found" in message for message in caplog.messages)


def test_register_custom_cards_skips_existing_lovelace_resources(tmp_path, monkeypatch):
    existing_url = "/local/community/huawei_charger/huawei-charger-control-card.js"
    resources = FakeResources([{"url": existing_url, "type": "module"}])
    hass = FakeHass(tmp_path, resources=resources)

    monkeypatch.setattr(huawei_init, "add_extra_js_url", lambda hass_arg, url: None)

    asyncio.run(huawei_init.register_custom_cards(hass))

    assert existing_url not in {item["url"] for item in resources.created}


def test_register_custom_cards_supports_lovelace_object_data(tmp_path, monkeypatch):
    existing_url = "/local/community/huawei_charger/huawei-charger-status-card.js"
    resources = FakeResources([FakeResourceItem(existing_url)])
    hass = FakeHass(tmp_path)
    hass.data["lovelace"] = FakeLovelaceData(resources)
    added_urls = []

    monkeypatch.setattr(huawei_init, "add_extra_js_url", lambda hass_arg, url: added_urls.append(url))

    asyncio.run(huawei_init.register_custom_cards(hass))

    assert existing_url not in {item["url"] for item in resources.created}
    assert len(resources.created) == len(huawei_init.CUSTOM_CARDS) - 1


def test_remove_legacy_platform_entities(monkeypatch):
    registry = SimpleNamespace(async_remove=MagicMock())
    entry = SimpleNamespace(entry_id="entry-1")
    registry_entries = [
        SimpleNamespace(
            domain="button",
            unique_id="entry-1_start_charge_button",
            entity_id="button.huawei_charger_start_charging",
        ),
        SimpleNamespace(
            domain="button",
            unique_id="entry-1_stop_charge_button",
            entity_id="button.huawei_charger_stop_charging",
        ),
        SimpleNamespace(
            domain="switch",
            unique_id="entry-1_charging_switch",
            entity_id="switch.huawei_charger_charging",
        ),
        SimpleNamespace(
            domain="sensor",
            unique_id="entry-1_sensor_10008",
            entity_id="sensor.huawei_charger_total_energy",
        ),
    ]

    monkeypatch.setattr(huawei_init.er, "async_get", lambda hass: registry)
    monkeypatch.setattr(
        huawei_init.er,
        "async_entries_for_config_entry",
        lambda registry_arg, entry_id: registry_entries,
    )

    asyncio.run(
        huawei_init._async_remove_legacy_platform_entities(SimpleNamespace(), entry)
    )

    assert registry.async_remove.call_args_list == [
        call("button.huawei_charger_start_charging"),
        call("button.huawei_charger_stop_charging"),
        call("switch.huawei_charger_charging"),
    ]
