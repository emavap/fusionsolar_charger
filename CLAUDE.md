# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a **Home Assistant custom integration** for **Huawei wallbox chargers** (SCharger 7kW/22kW) that connects through the FusionSolar portal API. It provides monitoring sensors and writable power control entities.

## Architecture

The integration follows Home Assistant's standard custom component structure:

- **Coordinator Pattern**: `coordinator.py` manages API authentication and data fetching using `DataUpdateCoordinator`
- **Config Flow**: `config_flow.py` handles user setup with credential validation
- **Platform Entities**: `sensor.py` (read-only metrics) and `number.py` (writable power controls)
- **Constants**: `const.py` defines register mappings and API endpoints
- **Custom Frontend**: `www/` contains JavaScript cards for enhanced dashboard experience

### Key Components

1. **HuaweiChargerCoordinator** (`coordinator.py:19`):
   - Authenticates with FusionSolar API
   - Fetches device parameter values via register IDs
   - Handles reauthentication on token expiry
   - Implements retry logic and error handling

2. **Entity Categories**:
   - **Main Sensors**: Core charging data (voltage, energy, status) - visible by default
   - **Diagnostic Sensors**: Technical/config data (device info, network settings) - hidden by default
   - **Number Entities**: Writable power limits with EEPROM protection

3. **Register System**: Device data accessed via numeric register IDs (e.g., "20012" = Charging Status)

## Development Commands

### Testing Integration
```bash
# Debug script requires credentials in environment variables
export FUSIONSOLAR_USERNAME='your_username'
export FUSIONSOLAR_PASSWORD='your_password'
python debug_integration.py
```

### Home Assistant Development
```bash
# Copy integration to HA config (development setup)
cp -r custom_components/huawei_charger /path/to/homeassistant/config/custom_components/

# Check HA logs for integration issues
tail -f /path/to/homeassistant/home-assistant.log | grep huawei_charger
```

## Critical Implementation Details

### API Authentication Flow
1. POST to `intl.fusionsolar.huawei.com:32800` with credentials
2. Extract `accessToken` and `regionFloatIp` from response
3. Use region IP for subsequent API calls
4. Handle token expiry with automatic reauthentication

### EEPROM Protection (`number.py:38-44`)
- **5-second debounce** delay for power limit changes
- **30-second minimum interval** between writes
- **Value deduplication** to prevent redundant writes
- Protects device memory from excessive write cycles

### Entity Availability Logic
- Simple check: `coordinator.last_update_success and coordinator.data.get(reg_id) is not None`
- Entities show as unavailable when register data is missing
- Clean failure handling via `UpdateFailed` exceptions

### Register Categories
- **Main sensors**: Essential charging info (always visible)
- **Diagnostic sensors**: Technical data (hidden by default via `EntityCategory.DIAGNOSTIC`)
- **Register mappings**: Defined in `REGISTER_NAME_MAP` with human-readable names

### Custom Frontend Cards
- Auto-registered during integration setup via `register_custom_cards()`
- Copied to HA `www/` directory automatically  
- Provides enhanced dashboard experience with real-time controls

## Configuration

### Required Credentials
- **Username**: FusionSolar portal login
- **Password**: FusionSolar portal password  
- **Update Interval**: Polling frequency (10-3600 seconds, default 30)

### Key Register IDs
- `538976598`: Fixed Max Charging Power (writable)
- `20001`: Dynamic Power Limit (writable)
- `20012`: Charging Status
- `20017`: Plugged In Status
- `10008`: Total Energy Charged
- `2101259-2101261`: Phase A/B/C Voltages

## Security Notes

- **SSL verification disabled** for FusionSolar API (required due to Huawei's server config)
- **No local credentials storage** - uses Home Assistant's secure config entry system
- **API rate limiting** implemented to respect service limits

## File Structure
```
custom_components/huawei_charger/
├── __init__.py           # Integration setup & custom card registration
├── manifest.json         # Integration metadata
├── config_flow.py        # User setup flow with validation
├── coordinator.py        # API client & data coordination
├── const.py             # Constants & register mappings  
├── sensor.py            # Read-only sensor entities
├── number.py            # Writable number entities (power limits)
├── services.yaml        # Service definitions
├── strings.json         # UI text translations
├── translations/en.json # English translations
└── www/                 # Custom Lovelace cards
    ├── README.md
    └── *.js            # JavaScript card implementations
```

## Common Issues

### Entity Shows "Unknown" Value
- Check register ID exists in device data via debug script
- Verify register name mapping in `const.py:REGISTER_NAME_MAP`
- Some registers may not be available on all device models

### Authentication Failures
- Verify credentials work in FusionSolar web portal
- Check if account has wallbox device permissions
- API may rate-limit after multiple failed attempts

### Slow Entity Updates  
- Default 30-second polling interval to avoid API rate limits
- Device responses can be slow (10+ seconds)
- Network connectivity to FusionSolar servers affects performance

## Known Working State
- This integration was working correctly at commit `b874845`
- Avoid overengineering error handling or availability logic
- Keep entity availability checks simple and predictable
- Use proper `UpdateFailed` exceptions for coordinator failures