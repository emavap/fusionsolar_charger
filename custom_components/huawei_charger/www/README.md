# Huawei Charger Custom Lovelace Cards

This directory contains custom Lovelace cards designed specifically for the Huawei Charger integration. These cards provide a rich, visual interface for monitoring and controlling your Huawei wallbox charger.

## Available Cards

### 1. Huawei Charger Status Card
**File**: `huawei-charger-status-card.js`

A comprehensive status card that displays:
- Real-time charging status with animated indicators
- Current power consumption with visual power bar
- Session energy and connection status
- Dynamic color coding based on charging state

### 2. Huawei Charger Control Card
**File**: `huawei-charger-control-card.js`

An interactive control panel featuring:
- Power limit slider with real-time adjustment
- Quick preset buttons (Eco, Normal, Fast, Max)
- Current settings display
- Visual feedback for active presets

### 3. Huawei Charger Energy Card
**File**: `huawei-charger-energy-card.js`

Energy monitoring dashboard with:
- Session energy and duration tracking
- Total energy consumption metrics
- Cost calculations (optional)
- Charging progress indicators
- Real-time power trends

### 4. Huawei Charger Info Card
**File**: `huawei-charger-info-card.js`

Device information and diagnostics:
- Device details (model, serial, versions)
- Health status indicators
- Temperature and lock status
- Voltage readings per phase
- Error and warning codes

## Installation

The integration auto-copies and auto-registers these Lovelace resources during setup. In a normal installation you do not need to manually copy the `.js` files or add dashboard resources yourself.

If your Home Assistant instance blocks automatic resource registration, the fallback resource URLs are:

```yaml
resources:
  - url: /local/community/huawei_charger/huawei-charger-status-card.js
    type: module
  - url: /local/community/huawei_charger/huawei-charger-control-card.js
    type: module
  - url: /local/community/huawei_charger/huawei-charger-energy-card.js
    type: module
  - url: /local/community/huawei_charger/huawei-charger-info-card.js
    type: module
```

## Usage Examples

### Basic Status Card
```yaml
# No configuration needed - auto-detects entities
type: custom:huawei-charger-status-card
```

### Control Card
```yaml
type: custom:huawei-charger-control-card
# Optional but recommended when you have multiple chargers:
# dynamic_power_entity: number.huawei_charger_dynamic_power_limit
# current_power_entity: sensor.huawei_charger_current_power
```

### Energy Card with Cost Tracking
```yaml
type: custom:huawei-charger-energy-card
show_cost: true
energy_cost: 0.15  # Cost per kWh
currency: "$"
```

### Info Card (Minimal)
```yaml
type: custom:huawei-charger-info-card
show_diagnostic: false
```

### Complete Dashboard Example
```yaml
type: vertical-stack
cards:
  - type: horizontal-stack
    cards:
      - type: custom:huawei-charger-status-card
      - type: custom:huawei-charger-control-card
  
  - type: horizontal-stack
    cards:
      - type: custom:huawei-charger-energy-card
        show_cost: true
        energy_cost: 0.12
        currency: "€"
      - type: custom:huawei-charger-info-card
        show_diagnostic: true
```

## Configuration Options

### Status Card
| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `device_status_entity` | string | auto-detected | Explicit charger status entity |
| `charge_store_entity` | string | auto-detected | Explicit station charge-store entity |
| `plugged_in_entity` | string | auto-detected | Explicit plugged/connected entity |
| `dynamic_power_entity` | string | auto-detected | Explicit power-limit entity |
| `current_power_entity` | string | optional | Manual override for a separate live power entity, if you have one |

### Control Card
| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `dynamic_power_entity` | string | auto-detected | Dynamic power limit entity |
| `fixed_power_entity` | string | auto-detected | Fixed power limit entity |
| `current_power_entity` | string | optional | Manual override for a separate live power entity, if you have one |
| `device_status_entity` | string | auto-detected | Explicit charger status entity |
| `charge_store_entity` | string | auto-detected | Explicit station charge-store entity |
| `plugged_in_entity` | string | auto-detected | Explicit plugged/connected entity |

### Energy Card
| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `show_cost` | boolean | `false` | Show cost calculations |
| `energy_cost` | number | `0.12` | Cost per kWh |
| `currency` | string | `€` | Currency symbol |
| `session_energy_entity` | string | `sensor.huawei_charger_session_energy` | Session energy entity |
| `current_power_entity` | string | optional | Manual override for a separate live power entity, if you have one |

### Info Card
| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `show_diagnostic` | boolean | `true` | Show diagnostic information |

## Features

### Visual Indicators
- **Animated charging pulse** when actively charging
- **Color-coded status** (green=charging, blue=connected, gray=idle)
- **Progressive power bars** showing current vs. maximum power
- **Health status badges** with error/warning indicators

### Interactive Elements
- **Real-time power slider** with instant visual feedback
- **Preset power buttons** for common charging scenarios
- **Expandable diagnostic section** to save space
- **Hover effects** and smooth transitions

### Smart Defaults
- **Automatic entity detection** based on integration naming
- **Dynamic power limits** read from device capabilities
- **Responsive grid layouts** that adapt to different screen sizes
- **Fallback values** when entities are unavailable

## Troubleshooting

### Cards Not Appearing
1. Check that resources are correctly added to Home Assistant
2. Verify file paths are correct (`/local/...`)
3. Check browser console for JavaScript errors
4. Clear browser cache and refresh

### Entity Not Found Errors
1. Verify your Huawei Charger integration is working
2. Check entity IDs in Developer Tools → States
3. Update card configuration with correct entity names
4. Ensure entities are available (not unavailable/unknown)

### Styling Issues
1. Check Home Assistant theme compatibility
2. Some custom themes may override card styles
3. Use browser developer tools to inspect CSS

## Customization

The cards are designed to inherit your Home Assistant theme colors automatically. Key design elements:

- **Primary colors** from your active theme
- **Card backgrounds** matching your dashboard
- **Consistent spacing** with Home Assistant design language
- **Responsive layouts** for mobile and desktop

For advanced customization, you can modify the CSS styles within each card file.

## Browser Compatibility

These cards are compatible with:
- Chrome 90+
- Firefox 88+
- Safari 14+
- Edge 90+

Older browsers may not support all features (CSS Grid, custom elements).
