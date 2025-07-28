# 🚗 Huawei Charger Dashboard Visualizations

This document provides pre-built dashboard card configurations for visualizing your Huawei charger data in Home Assistant.

## 📊 Available Dashboard Cards

### 1. **Main Status Card** - Essential charging information
- Current charging status and cable connection
- Temperature monitoring
- Power limit controls
- Clean, organized entity list

### 2. **Power & Voltage Gauges** - Visual meters
- Rated power gauge with color-coded zones
- Three-phase voltage monitoring
- Real-time needle indicators
- Color-coded safety zones (green/yellow/red)

### 3. **Energy Tracking** - Consumption monitoring
- Total lifetime energy charged
- Current session energy and duration
- Historical tracking with timestamps
- Phase voltage details

### 4. **Statistics Graph** - Historical analysis
- Weekly energy consumption patterns
- Statistical analysis (sum, max, average)
- Multi-sensor comparison
- Trend visualization

### 5. **Power Control Panel** - Management interface
- Adjustable power limits
- Real-time control capabilities
- Device specifications display
- Clean control interface

### 6. **Quick Glance View** - Minimal overview
- Compact 5-sensor display
- At-a-glance status
- Perfect for mobile dashboards
- Essential metrics only

### 7. **Advanced Multi-Column Layout** - Comprehensive view
- Structured 4-row layout
- Status, metrics, voltage, and controls
- Professional appearance
- Complete monitoring solution

### 8. **Temperature Monitoring** - Thermal management
- Thermostat-style display
- Temperature trends
- Safety monitoring
- Visual temperature representation

## 🚀 How to Use

### Step 1: Access Your Dashboard
1. Open Home Assistant
2. Go to **Overview** (main dashboard)
3. Click the **3-dot menu** (top right)
4. Select **Edit Dashboard**

### Step 2: Add Cards
1. Click **+ ADD CARD**
2. Select **Manual** (YAML editor)
3. Copy any card configuration from `dashboard_example.yaml`
4. Paste it into the card editor
5. Click **SAVE**

### Step 3: Customize
- Replace entity names if your entities have different IDs
- Adjust colors, ranges, and thresholds to your preferences
- Modify titles and icons as needed

## 🎨 Entity Names Reference

Make sure your entities match these names (adjust in YAML if different):

**Main Sensors:**
- `sensor.huawei_charger_charging_status`
- `sensor.huawei_charger_plugged_in`
- `sensor.huawei_charger_temperature`
- `sensor.huawei_charger_total_energy_charged`
- `sensor.huawei_charger_session_energy`
- `sensor.huawei_charger_session_duration`
- `sensor.huawei_charger_rated_power`
- `sensor.huawei_charger_phase_a_voltage`
- `sensor.huawei_charger_phase_b_voltage`
- `sensor.huawei_charger_phase_c_voltage`

**Control Entities:**
- `number.huawei_charger_fixed_max_charging_power`
- `number.huawei_charger_dynamic_power_limit`

## 🔧 Advanced Features

### Custom Cards (Optional)
Some configurations use advanced custom cards that provide enhanced visualizations:

1. **Sankey Chart** - Energy flow visualization
   - Install via HACS: [ha-sankey-chart](https://github.com/MindFreeze/ha-sankey-chart)
   - Shows energy flow from grid → charger → vehicle

2. **Button Card** - Enhanced control buttons
   - Install via HACS: [button-card](https://github.com/custom-cards/button-card)
   - Provides emergency stop functionality

### Color Coding Guide
- 🟢 **Green**: Normal operation, safe values
- 🟡 **Yellow**: Caution, approaching limits  
- 🔴 **Red**: Warning, at or exceeding limits
- 🔵 **Blue**: Information, neutral status

## 📱 Mobile Optimization

For mobile dashboards, recommend using:
- **Quick Glance View** - Compact overview
- **Main Status Card** - Essential information
- **Power Control Panel** - Easy adjustments

## 🛠️ Troubleshooting

### Entity Not Found
If you see "Entity not available":
1. Check that the Huawei Charger integration is working
2. Verify entity names in **Developer Tools** → **States**
3. Update entity names in the YAML configuration

### Card Not Displaying
1. Check YAML syntax for errors
2. Ensure all required entities exist
3. Try simpler card configurations first

### Custom Cards Not Working
1. Install required custom cards via HACS
2. Restart Home Assistant after installation
3. Clear browser cache

## 💡 Tips & Best Practices

1. **Start Simple**: Begin with basic cards, then add advanced features
2. **Test First**: Use a test dashboard to experiment with layouts
3. **Mobile First**: Design for mobile, then adapt for desktop
4. **Monitor Performance**: Too many cards can slow down dashboards
5. **Regular Updates**: Update card configurations as your needs change

## 🔗 Related Documentation

- [Home Assistant Dashboard Documentation](https://www.home-assistant.io/dashboards/)
- [Card Configuration Reference](https://www.home-assistant.io/dashboards/cards/)
- [HACS Custom Cards](https://hacs.xyz/categories/frontend/)

---

**Enjoy your enhanced Huawei charger monitoring experience! 🚗⚡**