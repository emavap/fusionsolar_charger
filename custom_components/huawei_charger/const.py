DOMAIN = "huawei_charger"
CONF_INTERVAL = "update_interval"

# Writable registers
REG_FIXED_MAX_POWER = "538976598"
REG_DYNAMIC_POWER_LIMIT = "20001"

# Register name mapping
REGISTER_NAME_MAP = {
    REG_FIXED_MAX_POWER: "Fixed Max Charging Power",
    REG_DYNAMIC_POWER_LIMIT: "Dynamic Power Limit",
    "538976516": "Device IP",
    # "2101260": "Session Energy",
    "2101259": "Phase A Voltage",
    # "2101261": "Total Energy",
    # "20014": "Charging State",
    "20016": "Charging Enabled",
    "20011": "Device Name",
    "20010": "Charging Mode",
    # "10035": "A Output Current",
    "10008": "Total Energy Charged",
    "10001": "Software Version",
    "20013": "Lock Status",
    "20017": "Plugged In",
    "20029": "Device Serial Number"
}