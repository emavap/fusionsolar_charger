CONNECTED_STATE_VALUES = {
    "1",
    "2",
    "3",
    "4",
    "6",
    "8",
    "10",
    "11",
    "true",
    "connected",
    "plugged",
    "plugged_in",
    "ready",
    "charging",
    "active",
}

DISCONNECTED_STATE_VALUES = {
    "0",
    "97",
    "98",
    "99",
    "false",
    "disconnected",
    "unplugged",
    "not_connected",
    "idle",
    "none",
}

CHARGING_STATE_VALUES = {
    "3",
    "11",
    "charging",
    "active",
}

NOT_CHARGING_STATE_VALUES = {
    "0",
    "1",
    "2",
    "4",
    "5",
    "6",
    "7",
    "8",
    "9",
    "10",
    "97",
    "98",
    "99",
    "false",
    "connected",
    "plugged",
    "plugged_in",
    "ready",
    "idle",
    "paused",
    "stopped",
}


def normalize_state(value):
    return str(value).strip().lower() if value is not None else None


def is_connected_state(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0

    normalized = normalize_state(value)
    if not normalized:
        return None
    if normalized in CONNECTED_STATE_VALUES:
        return True
    if normalized in DISCONNECTED_STATE_VALUES:
        return False
    return None


def vehicle_connected_state(coordinator):
    raw_plugged = coordinator.get_register_value("20017")
    plugged_state = is_connected_state(raw_plugged)
    if plugged_state is not None:
        return plugged_state, "20017"

    for reg_id in ("device_status", "charge_store"):
        reg_value = coordinator.get_register_value(reg_id)
        derived_state = is_connected_state(reg_value)
        if derived_state is not None:
            return derived_state, reg_id

    return None, None


def is_charging_state(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value > 0

    normalized = normalize_state(value)
    if not normalized:
        return None
    if normalized in CHARGING_STATE_VALUES:
        return True
    if normalized in NOT_CHARGING_STATE_VALUES:
        return False
    return None


def charging_state(coordinator):
    for reg_id in ("device_status", "charge_store"):
        reg_value = coordinator.get_register_value(reg_id)
        derived_state = is_charging_state(reg_value)
        if derived_state is not None:
            return derived_state, reg_id

    return None, None
