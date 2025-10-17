import pytest

from custom_components.huawei_charger.coordinator import HuaweiChargerCoordinator


@pytest.fixture
def coordinator():
    # Bypass __init__ to focus on conversion helpers
    return object.__new__(HuaweiChargerCoordinator)


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("42", 42),
        ("7.4", pytest.approx(7.4)),
        ("231.0", 231),
        ("-15.5", pytest.approx(-15.5)),
        ("   -50   ", -50),
    ],
)
def test_convert_register_value_numeric(coordinator, raw, expected):
    result = coordinator._convert_register_value(raw)
    assert result == expected


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("true", True),
        ("FALSE", False),
        ("Unknown", "Unknown"),
        ("", ""),
        ("    ", ""),
        ("0.0.0", "0.0.0"),
    ],
)
def test_convert_register_value_non_numeric(coordinator, raw, expected):
    result = coordinator._convert_register_value(raw)
    assert result == expected


def test_convert_register_value_passthrough_types(coordinator):
    assert coordinator._convert_register_value(5) == 5
    assert coordinator._convert_register_value(3.2) == 3.2
    assert coordinator._convert_register_value(True) is True


def test_normalize_param_values_dict_only(coordinator):
    assert coordinator._normalize_param_values(None) == {}
    assert coordinator._normalize_param_values(["not", "dict"]) == {}


def test_normalize_param_values_conversions(coordinator):
    raw = {
        "2101259": "231.0",
        "538976598": "7.4",
        "20014": " 25.0 ",
        "20015": "Unknown",
        "20016": "",
        "20017": "true",
        "20018": "0.0.0",
    }
    normalized = coordinator._normalize_param_values(raw)

    assert normalized["2101259"] == 231
    assert normalized["538976598"] == pytest.approx(7.4)
    assert normalized["20014"] == 25
    assert normalized["20015"] == "Unknown"
    assert normalized["20016"] == ""
    assert normalized["20017"] is True
    assert normalized["20018"] == "0.0.0"

