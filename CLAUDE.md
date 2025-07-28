# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Home Assistant custom integration for Huawei SCharger wallbox chargers (7kW/22kW). The integration connects to Huawei's FusionSolar platform to monitor and control wallbox charging parameters through the cloud API.

## Architecture

The integration follows Home Assistant's standard structure:

- **Entry Point**: `__init__.py` - Handles component setup/teardown, defines platforms (sensor, number)
- **Data Coordinator**: `coordinator.py` - Core logic for authentication, API communication, and data fetching
- **Config Flow**: `config_flow.py` - User configuration interface for credentials and settings
- **Entity Platforms**: 
  - `sensor.py` - Read-only entities (device info, energy, voltage, etc.)
  - `number.py` - Writable entities for power limits (Fixed Max Power, Dynamic Power Limit)

### Key Components

1. **HuaweiChargerCoordinator** (`coordinator.py:19`): 
   - Manages FusionSolar authentication with automatic token refresh
   - Handles 3-tier API calls: auth → station list → device parameters
   - Implements retry logic for failed requests
   - Provides `set_config_value()` method for writing parameters

2. **Authentication Flow**:
   - Authenticates against `intl.fusionsolar.huawei.com`
   - Retrieves region IP and access tokens
   - Fetches station DN (device identifier)
   - Accesses wallbox parameters through device API

3. **Entity Structure**:
   - Sensors expose read-only register values (defined in `INTERESTING_SENSOR_REGISTERS`)
   - Number entities allow setting power limits within 1.6-7.4kW range
   - All entities use coordinator pattern for data updates

## Register System

The wallbox uses numeric register IDs for parameters:
- **Writable**: `538976598` (Fixed Max Power), `20001` (Dynamic Power Limit)
- **Read-only**: Extensive set including power, current, voltage, energy, and session data
- Register mappings defined in `REGISTER_NAME_MAP` (`const.py:9`)

### Key Registers Added:
- **Power**: `2101001` (Current Power), `20021` (Rated Power)
- **Current**: `2101002-2101004` (Phase A/B/C Current), `20019-20020` (Max/Min Current)
- **Voltage**: `2101260-2101261` (Phase B/C Voltage)
- **Energy**: `10009` (Session Energy), `10010` (Session Duration)
- **Status**: `20012` (Charging Status), `20014` (Temperature), `20015-20016` (Error/Warning Codes)
- **Session**: `20024-20025` (Session Start/End Time)
- **Safety**: `20027-20028` (Ground Status, Insulation Resistance)

## Development

### Testing
No formal test suite exists. Manual testing requires:
1. Valid FusionSolar credentials
2. Access to a Huawei wallbox device
3. Home Assistant development environment

### Configuration
The integration uses Home Assistant's config flow system:
- Username/password for FusionSolar account  
- Update interval (default: 30 seconds)
- All configuration stored in HA's config entries

### API Behavior
- Uses unverified HTTPS requests (`verify=False`)
- Implements exponential backoff for retries
- 10-second delay after parameter changes before refresh
- Automatic reauthentication on token expiry
- Enhanced logging shows available register IDs for debugging

### Sensor Configuration
- Sensors automatically configured with proper units and device classes
- Value conversion for power (W→kW), time (s→min), power factor (decimal→%)
- Availability based on successful coordinator updates and non-null values
- Raw values exposed in state attributes for debugging

## File Structure
```
custom_components/huawei_charger/
├── __init__.py          # Component setup
├── coordinator.py       # API client and data coordination  
├── config_flow.py       # Configuration interface
├── sensor.py           # Read-only entities
├── number.py           # Writable power limit entities
├── const.py            # Constants and register mappings
├── manifest.json       # Integration metadata
└── strings.json        # UI text translations
```