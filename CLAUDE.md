# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a **Home Assistant Custom Integration** for monitoring and controlling Huawei SCharger wallbox chargers through the FusionSolar API. The integration provides real-time monitoring of charging status, power consumption, and allows remote control of charging power limits.

## Development Commands

Since this is a Home Assistant custom integration, there are no traditional build/test commands. Development workflow involves:

1. **Installation Testing**: Copy the `custom_components/huawei_charger` folder to a Home Assistant instance's custom_components directory and restart HA
2. **Validation**: Use Home Assistant's built-in component validation when loading the integration
3. **Logging**: Enable debug logging in Home Assistant configuration.yaml:
   ```yaml
   logger:
     logs:
       custom_components.huawei_charger: debug
   ```

## Architecture Overview

### Core Components

**Data Flow Architecture:**
- `coordinator.py` - Central data coordinator using Home Assistant's DataUpdateCoordinator pattern
  - Handles authentication with FusionSolar API
  - Manages periodic data fetching and automatic token refresh
  - Implements retry logic with exponential backoff
  - Provides unified data access for all entities

**Entity Types:**
- `sensor.py` - Read-only sensors (voltage, energy, status, temperature)
  - Split into main sensors (visible by default) and diagnostic sensors (hidden)
  - Uses register mapping from const.py for human-readable names
- `number.py` - Writable power control entities with EEPROM protection
  - Implements debouncing and rate limiting to protect device memory
  - Supports both Fixed Max Power (register 538976598) and Dynamic Power Limit (register 20001)

**Configuration:**
- `config_flow.py` - Handles user setup and credential validation
- `const.py` - Central registry of device registers and their mappings
- `__init__.py` - Integration setup, platform forwarding, and custom card registration

### Key Technical Details

**Authentication Flow:**
1. Username/password → FusionSolar token endpoint
2. Token → Regional server IP discovery  
3. Station DN lookup → Device DN discovery
4. Device DN → Register value fetching/setting

**Register System:**
The device exposes configuration and sensor data through numbered registers. Key registers:

*Main Sensors (visible by default):*
- `2101259` - Phase A Voltage
- `2101260` - Phase B Voltage  
- `2101261` - Phase C Voltage
- `10008` - Total Energy Charged
- `10009` - Session Energy
- `10010` - Session Duration
- `20012` - Charging Status
- `20017` - Plugged In
- `10003` - Rated Power
- `2101271` - Internal Temperature

*Writable Control Registers:*
- `538976598` - Fixed Max Charging Power (writable)
- `20001` - Dynamic Power Limit (writable)

*Diagnostic Registers (hidden by default):*
Device identification: `20011`, `10001`, `10002`, `20029`, `2101252`, `2101251`, `10007`, `10012`
Status/error codes: `20013`, `20015`, `20016`, `20014`, `15101`
Network/IP config: `538976516`, `2101760`, `2101763`, `2101524`, `2101526`, `538976280`, `538976281`, `538976533`, `538976534`
Power config: `538976569`, `538976570`, `538976576`
System config: `10047`, `538976288`, `538976289`, `538976308`, `538976515`, `538976517`, `538976518`, `538976519`, `538976520`, `538976558`, `538976790`, `538976800`
Extended/reserved: `10035`, `10034`, `10100`, `538976523`, `538976564`, `538976568`, `539006279`, `539006281`, `539006282`, `539006283`, `539006284`, `539006285`, `539006286`, `539006287`, `539006288`, `539006290`, `539006291`, `539006292`, `539006293`

**EEPROM Protection:**
The number entities implement sophisticated protection against wearing out the device's memory:
- 5-second debouncing delay before writing values
- 30-second minimum interval between writes
- Value comparison to avoid duplicate writes
- Async task management for pending writes

### Custom Frontend Cards

The integration includes 4 custom Lovelace cards (in `www/` directory):
- **Status Card**: Real-time charging status and cable connection
- **Control Card**: Power limit adjustment interface
- **Energy Card**: Energy consumption tracking and statistics  
- **Info Card**: Device information and technical specifications

Cards are automatically registered with Home Assistant's frontend during integration setup.

### Integration Patterns

**Home Assistant Best Practices:**
- Uses DataUpdateCoordinator for efficient data management
- Implements proper device_info for device registry
- Follows entity naming conventions with unique_id generation
- Supports config flow for user-friendly setup
- Includes proper error handling and logging
- Uses entity categories (diagnostic) for UI organization

**API Communication:**
- FusionSolar API uses HTTPS with token-based authentication
- Handles regional server routing automatically
- Implements proper session management with cookies
- Uses application/json for auth, application/x-www-form-urlencoded for device operations

## Key Files and Locations

- `custom_components/huawei_charger/coordinator.py:19` - Main HuaweiChargerCoordinator class
- `custom_components/huawei_charger/const.py:9` - REGISTER_NAME_MAP with all device registers
- `custom_components/huawei_charger/number.py:46` - Power limit validation logic
- `custom_components/huawei_charger/__init__.py:21` - Custom card registration system
- `dashboard_example.yaml` - Complete dashboard configuration examples
- `DASHBOARD.md` - Comprehensive dashboard setup documentation

## Important Considerations

**Device Communication:**
- The integration communicates with Huawei's cloud API, not directly with the device
- Requires valid FusionSolar account credentials
- Update intervals should be reasonable (30+ seconds) to avoid API rate limiting
- Device must be properly configured in FusionSolar portal

**Power Control Safety:**
- Power limit changes are rate-limited to protect device EEPROM
- Values are validated against device capabilities before sending
- The integration supports both 7kW and 22kW charger variants
- Always verify power limits match your electrical installation capacity

**Home Assistant Integration:**
- Requires Home Assistant 2023.0.0 or later
- Custom cards require browser refresh after first installation
- Integration data persists across Home Assistant restarts
- Supports HACS (Home Assistant Community Store) for easy installation