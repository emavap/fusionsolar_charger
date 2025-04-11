# 🔌 Huawei Charger Integration for Home Assistant

This custom integration allows you to monitor and control your **Huawei SCharger 7kW / 22kW** wallbox charger using Home Assistant.

---

## ✨ Features

- ✅ **Authentication** via FusionSolar credentials
- 🔁 **Automatic reauthentication** on token expiry
- 🔄 **Periodic updates** with configurable interval
- 📊 **Sensor Entities** for:
  - Device IP
  - Charging State
  - Charging Mode
  - Total Energy, Session Energy
  - Output Current, Phase A Voltage
  - Software Version and more
- 🔢 **Number Entities** (writable) for:
  - Fixed Max Charging Power (`538976598`)
  - Dynamic Power Limit (`20001`)

---

## 📦 Installation (via HACS)

1. Add this repository to HACS as a [custom integration](https://hacs.xyz/docs/faq/custom_repositories/)
2. Reboot Home Assistant
3. Go to **Settings > Devices & Services > Integrations**
4. Click **“Add Integration”** and search for `Huawei Charger`
5. Enter your FusionSolar credentials and preferred update interval

---

## ⚙️ Configuration Options

| Option         | Description                                |
|----------------|--------------------------------------------|
| Username       | FusionSolar portal username                |
| Password       | FusionSolar portal password                |
| Update Interval| How often to poll charger data (seconds)   |

---

## 🧪 Tested With

- Huawei SCharger-7KS-S0
- Home Assistant 2024.2+

---

## 📚 Entity Overview

| Entity Type | Description                          |
|-------------|--------------------------------------|
| Sensor      | Read-only metrics from the wallbox   |
| Number      | Configurable power limit registers   |

---

## 📥 Issues or Contributions

Please open a GitHub issue if you have problems or would like to contribute!

---

## ✅ License

MIT License
