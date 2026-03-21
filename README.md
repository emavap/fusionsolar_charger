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

## Logging

Detailed Huawei logging is optional. When enabled, the integration logs sanitized request and response data for:

- authentication
- station discovery
- wallbox realtime data
- config signal reads
- config signal writes

Sensitive values such as passwords, tokens, cookies, and CSRF-style values are redacted before logging.

## Tested With

- Huawei SCharger-7KS-S0
- Home Assistant 2024.2+

## Notes

- The integration uses the newer FusionSolar wallbox config endpoints for writable settings.
- Existing automations can keep using the same writable entity IDs after upgrading.

## License

MIT License
