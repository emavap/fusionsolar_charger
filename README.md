# Huawei Charger Integration for Home Assistant

This custom integration monitors and controls Huawei SCharger wallboxes through the current FusionSolar cloud flow, including tenant-specific `uni...fusionsolar.huawei.com` hosts.

## Features

- FusionSolar cloud authentication with automatic reauthentication
- Support for tenant hostnames or full FusionSolar URLs
- Configurable polling interval and optional detailed Huawei request logging
- Writable charger controls that keep stable Home Assistant entity IDs:
  - Fixed Max Charging Power (`538976598`)
  - Dynamic Power Limit (`20001`)
- Runtime and diagnostic entities sourced from the newer FusionSolar wallbox endpoints
- Diagnostic entities for update status, write status, and reauthentication state

## Installation

1. Add this repository to HACS as a [custom integration](https://hacs.xyz/docs/faq/custom_repositories/).
2. Restart Home Assistant.
3. Go to `Settings > Devices & Services > Integrations`.
4. Add `Huawei Charger`.
5. Enter your FusionSolar username, password, host or full FusionSolar URL, and preferred update interval.

## Configuration

Initial setup fields:

| Option | Description |
|--------|-------------|
| Username | FusionSolar portal username |
| Password | FusionSolar portal password |
| FusionSolar Host or URL | Tenant hostname or full FusionSolar URL, for example `uni005eu5.fusionsolar.huawei.com` |
| Update Interval | Poll interval in seconds |
| Verify SSL certificates | Enable TLS certificate verification |
| Enable detailed Huawei logging | Logs sanitized Huawei request and response details for troubleshooting |

Common FusionSolar host values:

- Older shared host: `intl.fusionsolar.huawei.com`
- Newer tenant hosts: `uni005eu5.fusionsolar.huawei.com` and other `uni...fusionsolar.huawei.com` variants
- You can paste either the hostname itself or the full browser URL from FusionSolar; the integration will extract the host automatically

After setup:

- Use `Options` to change the poll interval, SSL verification, or detailed logging.
- Use `Reconfigure` to change the FusionSolar host.
- Use `Reauthenticate` when credentials are rejected.

## Entities

The integration only creates entities for charger values actually returned by Huawei, so stale unavailable sensors from older payloads are cleaned up on reload.

Important entities:

- `number.huawei_charger_fixed_max_charging_power`
- `number.huawei_charger_dynamic_power_limit`
- `sensor.huawei_charger_debug_update_status`
- `sensor.huawei_charger_debug_write_status`
- `binary_sensor.huawei_charger_reauthentication_required`

Diagnostic service:

- `huawei_charger.start_charge`
  - Calls FusionSolar's charger session start endpoint
  - Uses `gun_number` 1 by default
  - Accepts an optional `account_id` override if your tenant requires it
- `huawei_charger.stop_charge`
  - Calls FusionSolar's charger session stop endpoint
  - Uses `gun_number` 1 by default
  - Automatically resolves the active `orderNumber` and `serialNumber` from live process data when possible
- `huawei_charger.dump_config_signals`
  - Refreshes the charger config-signal catalog
  - Logs a `session_control_candidates` section based on signal names/options
  - Logs the full config-signal catalog returned by Huawei for reverse engineering
- `huawei_charger.set_config_signal`
  - Writes an arbitrary Huawei config signal through the same FusionSolar cloud endpoint used for existing writable controls
  - Intended for testing hidden start/stop, mode, authorization, or scheduling signals discovered by `dump_config_signals`

## Logging

Detailed Huawei logging is optional. When enabled, the integration logs sanitized request and response data for:

- authentication
- station discovery
- charger start/stop actions
- charger process-data lookups
- wallbox realtime data
- config signal reads
- config signal writes

To start charging from Developer Tools > Actions:

```yaml
action: huawei_charger.start_charge
data:
  gun_number: 1
```

To stop charging:

```yaml
action: huawei_charger.stop_charge
data:
  gun_number: 1
```

If your FusionSolar tenant rejects `start_charge`, try again with an explicit `account_id`. If `stop_charge` cannot infer the active session metadata, you can also pass `order_number` and `serial_number` manually.

To inspect potential hidden start/stop fields, call `huawei_charger.dump_config_signals` from Developer Tools > Actions after a successful refresh. The service writes the results to the Home Assistant log and highlights likely session-control signals such as working modes, authorization, scheduling, or enable/disable fields.

Once you find a plausible candidate, test it with `huawei_charger.set_config_signal` from Developer Tools > Actions. Example payload:

```yaml
action: huawei_charger.set_config_signal
data:
  param_id: "30001"
  value: "1"
```

Then inspect:

- `sensor.huawei_charger_debug_write_status`
- the Home Assistant log output for `set_config_signal`
- charger behavior in FusionSolar

Sensitive values such as passwords, tokens, cookies, and CSRF-style values are redacted before logging.

## Tested With

- Huawei SCharger-7KS-S0
- Home Assistant 2024.2+

## Notes

- The integration uses the newer FusionSolar wallbox config endpoints for writable settings.
- Existing automations can keep using the same writable entity IDs after upgrading.

## License

MIT License
