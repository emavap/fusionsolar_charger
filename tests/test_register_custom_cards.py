import asyncio
import importlib
from pathlib import Path

huawei_init = importlib.import_module("custom_components.huawei_charger.__init__")


class FakeConfig:
    def __init__(self, base_path: Path):
        self._base_path = base_path

    def path(self, relative: str) -> str:
        return str(self._base_path / relative)


class FakeHass:
    def __init__(self, base_path: Path):
        self.config = FakeConfig(base_path)
        self.data = {}

    async def async_add_executor_job(self, func, *args, **kwargs):
        return func(*args, **kwargs)


def test_register_custom_cards_copies_once(tmp_path, monkeypatch):
    hass = FakeHass(tmp_path)
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
    assert hass.data[huawei_init.DOMAIN]["_cards_registered"] is True

    asyncio.run(huawei_init.register_custom_cards(hass))
    assert added_urls == [
        f"/local/community/huawei_charger/{card}" for card in huawei_init.CUSTOM_CARDS
    ]


def test_register_custom_cards_handles_missing(tmp_path, monkeypatch, caplog):
    hass = FakeHass(tmp_path)
    added_urls = []

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
    assert any("Custom card file not found" in message for message in caplog.messages)
