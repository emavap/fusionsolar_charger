from homeassistant.const import CONF_HOST

DOMAIN = "huawei_charger"
CONF_INTERVAL = "update_interval"
CONF_VERIFY_SSL = "verify_ssl"
CONF_ENABLE_LOGGING = "enable_logging"

DEFAULT_REQUEST_TIMEOUT = 15
DEFAULT_LOCALE = "de_DE"
DEFAULT_TIMEZONE_OFFSET = 120  # +2:00 fallback
DEFAULT_FUSIONSOLAR_HOST = "intl.fusionsolar.huawei.com"
DEFAULT_ENABLE_LOGGING = False

# Writable registers
REG_FIXED_MAX_POWER = "538976598"
REG_DYNAMIC_POWER_LIMIT = "20001"
WRITABLE_REGISTERS = [REG_FIXED_MAX_POWER, REG_DYNAMIC_POWER_LIMIT]
SENSITIVE_REGISTERS = ["20034"]

# Register name mapping
REGISTER_NAME_MAP = {
    "current_power": "Current Power",
    REG_FIXED_MAX_POWER: "Fixed Max Charging Power",
    REG_DYNAMIC_POWER_LIMIT: "Dynamic Power Limit",
    "10001": "Software Version",
    "10002": "Hardware Version",
    "10003": "Rated Charging Power",
    "10008": "Total Energy Charged",
    "10007": "Model",
    "10012": "Bluetooth Name",
    "20012": "Main Breaker Rated Current",
    "20013": "Grounding System",
    "20014": "Network Mode",
    "20015": "Alias",
    "20029": "ESN",
    "20034": "Authentication Password",
    "33595393": "Device Name",
    "33595395": "Plant",
    "33595396": "Type",
    "538976515": "DHCP",
    "538976516": "IP Address",
    "538976517": "Subnet Mask",
    "538976518": "Gateway Address",
    "538976519": "Primary DNS",
    "538976520": "Secondary DNS",
    "538976790": "Allow Version Rollback",
    "539006279": "Channel IP Address",
    "539006286": "Encrypt Type",
    "539006287": "Authentication Type",
    "539006290": "Pack Frequency",
    "539006292": "Version Description",
    "539006293": "Description"
}
