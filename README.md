# OctoPrint-TuyaSmartplug

Control [Tuya-based](https://en.tuya.com/) smart plugs from OctoPrint — toggle power from the web UI or via GCODE commands.

This is a fork of [ziirish/OctoPrint-TuyaSmartplug](https://github.com/ziirish/OctoPrint-TuyaSmartplug), originally based on [OctoPrint-TPLinkSmartplug](https://github.com/jneilliii/OctoPrint-TPLinkSmartplug) and [python-tuya](https://github.com/clach04/python-tuya).

## What changed in this fork

- **Replaced the bundled `pytuya` library with [tinytuya](https://github.com/jasonacox/tinytuya)** — supports Tuya protocols 3.1, 3.2, 3.3, 3.4, and 3.5 (the original only supported 3.1 and 3.3)
- **Protocol version selector** — choose your device's protocol version from a dropdown instead of a simple v3.3 checkbox
- **Compatible with OctoPrint 1.11+** — removed deprecated `user_permission` import, added `is_api_protected()` declaration
- **Python 3 only** — dropped Python 2 support and dead code
- **Better error handling and logging** — device errors are reported with useful context (IP, device ID, protocol version, error codes) instead of silent failures

## Setup

Install via the bundled [Plugin Manager](https://docs.octoprint.org/en/master/bundledplugins/pluginmanager.html) using this URL:

```
https://github.com/msupino/OctoPrint-TuyaSmartplug/archive/master.zip
```

Or install manually:

```bash
pip install https://github.com/msupino/OctoPrint-TuyaSmartplug/archive/master.zip
```

## Requirements

- OctoPrint 1.9+ (tested on 1.11.7)
- Python 3.7+
- [tinytuya](https://github.com/jasonacox/tinytuya) (installed automatically)

## Getting your Device ID and Local Key

You need three pieces of information for each Tuya device:

| Setting | Description |
|---------|-------------|
| **IP Address** | Local network IP of the device |
| **Device ID** | Unique identifier from the Tuya platform |
| **Local Key** | AES encryption key for local communication |
| **Protocol Version** | 3.1, 3.2, 3.3, 3.4, or 3.5 |
| **Slot** | DPS index for the relay (usually 1) |

The easiest way to get these is with tinytuya's built-in wizard:

```bash
python -m tinytuya wizard
```

This will prompt you for your [Tuya IoT Platform](https://iot.tuya.com/) API credentials and return all device IDs and keys. See the [tinytuya setup guide](https://github.com/jasonacox/tinytuya#setup-wizard---getting-local-keys) for detailed instructions.

You can also auto-detect your device's protocol version:

```bash
python -m tinytuya scan
```

> **Note:** The Local Key changes if you remove and re-add a device in the Tuya/Smart Life app. You'll need to re-run the wizard if that happens.

## Configuration

After installing, go to **Settings → Tuya Smartplug** in OctoPrint:

1. Click the **+** button to add a plug (or the pencil icon to edit)
2. Fill in **IP**, **Device ID**, **Local Key**, and **Label**
3. Select the correct **Protocol Version** (try 3.5 first for newer devices, 3.3 for older ones)
4. Set the **Smart Outlet Slot** (usually `1` for single-outlet plugs)
5. Save

The plug icon will appear in the OctoPrint navbar. Click it to toggle power.

## GCODE Commands

When GCODE triggering is enabled for a plug, you can control it from GCODE:

| Command | Action |
|---------|--------|
| `M80 <label>` | Turn on |
| `M81 <label>` | Turn off |
| `G4 P1 <label>` | Turn on (alternative) |
| `G4 P2 <label>` | Turn off (alternative) |

Replace `<label>` with the plug's label or IP address as configured in settings.

## Troubleshooting

Enable **debug logging** in the plugin settings. Detailed logs are written to `plugin_tuyasmartplug_debug.log` in OctoPrint's log directory.

Common issues:

- **"Check device key or version" (error 914):** Wrong Local Key or wrong protocol version. Re-run `python -m tinytuya wizard` to get the current key, and try different protocol versions.
- **"Network Error: Device Unreachable" (error 905):** Device is offline or IP has changed. Check your router's DHCP leases.
- **Commands succeed but device doesn't respond physically:** Wrong DPS slot. Try slot `1` or `2` instead of the default.

## Credits

- [jneilliii](https://github.com/jneilliii) — original TPLinkSmartplug plugin
- [ziirish](https://github.com/ziirish) — Tuya adaptation
- [jasonacox](https://github.com/jasonacox) — tinytuya library
