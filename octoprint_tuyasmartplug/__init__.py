import octoprint.plugin
import os
import threading
import time

import tinytuya

VALID_VERSIONS = [3.1, 3.2, 3.3, 3.4, 3.5]
AUTO_DETECT_ORDER = [3.5, 3.4, 3.3, 3.1]


class tuyasmartplugPlugin(
    octoprint.plugin.SettingsPlugin,
    octoprint.plugin.AssetPlugin,
    octoprint.plugin.TemplatePlugin,
    octoprint.plugin.SimpleApiPlugin,
    octoprint.plugin.StartupPlugin,
    octoprint.plugin.ShutdownPlugin,
):
    # ~~ StartupPlugin mixin

    def on_startup(self, host, port):
        self._listeners = {}
        self._listener_stop = threading.Event()

    def on_after_startup(self):
        self._logger.info("TuyaSmartplug loaded! (tinytuya %s)", tinytuya.version)
        for plug in self._settings.get(["arrSmartplugs"]):
            if plug.get("label"):
                self._logger.info(
                    "Configured plug: '%s' ip=%s id=%s slot=%s version=%s",
                    plug["label"],
                    plug["ip"],
                    plug["id"],
                    plug["slot"],
                    plug.get("protocolVersion", "?"),
                )
        if self._settings.get(["statusMonitor"]) == "listener":
            self._start_listeners()

    # ~~ ShutdownPlugin mixin

    def on_shutdown(self):
        self._stop_listeners()

    # ~~ SettingsPlugin mixin

    def get_settings_defaults(self):
        return dict(
            arrSmartplugs=[
                {
                    "ip": "",
                    "id": "",
                    "slot": 1,
                    "localKey": "",
                    "label": "",
                    "icon": "icon-bolt",
                    "displayWarning": True,
                    "warnPrinting": False,
                    "gcodeEnabled": False,
                    "protocolVersion": "auto",
                    "gcodeOnDelay": 0,
                    "gcodeOffDelay": 0,
                    "autoConnect": True,
                    "autoConnectDelay": 10.0,
                    "autoDisconnect": True,
                    "autoDisconnectDelay": 0,
                    "linkedPlugs": "",
                    "sysCmdOn": False,
                    "sysRunCmdOn": "",
                    "sysCmdOnDelay": 0,
                    "sysCmdOff": False,
                    "sysRunCmdOff": "",
                    "sysCmdOffDelay": 0,
                    "currentState": "unknown",
                    "btnColor": "#808080",
                    "useCountdownRules": False,
                    "countdownOnDelay": 0,
                    "countdownOffDelay": 0,
                }
            ],
            statusMonitor="listener",
            pollingInterval=15,
        )

    def get_settings_restricted_paths(self):
        return dict(admin=[["arrSmartplugs"]])

    def on_settings_save(self, data):
        octoprint.plugin.SettingsPlugin.on_settings_save(self, data)

        plugs = self._settings.get(["arrSmartplugs"])
        self._logger.info("Settings saved, %d plug(s) configured.", len(plugs))
        for plug in plugs:
            if plug.get("label"):
                self._logger.info(
                    "  Plug '%s': ip=%s, id=%s, slot=%s, version=%s",
                    plug["label"],
                    plug["ip"],
                    plug["id"],
                    plug["slot"],
                    plug.get("protocolVersion", "?"),
                )
        monitor = self._settings.get(["statusMonitor"])
        if monitor == "listener":
            self._restart_listeners()
        else:
            self._stop_listeners()

    def get_settings_version(self):
        return 4

    def on_settings_migrate(self, target, current=None):
        if current is None or current < 3:
            self._logger.debug("Resetting arrSmartplugs for tuyasmartplug settings.")
            self._settings.set(
                ["arrSmartplugs"], self.get_settings_defaults()["arrSmartplugs"]
            )
        elif current == 3:
            plugs = self._settings.get(["arrSmartplugs"])
            if plugs:
                for plug in plugs:
                    if "v33" in plug:
                        plug["protocolVersion"] = "3.3" if plug.pop("v33") else "3.1"
                self._settings.set(["arrSmartplugs"], plugs)
                self._logger.info(
                    "Migrated v33 flag to protocolVersion for %d plug(s).", len(plugs)
                )

    # ~~ AssetPlugin mixin

    def get_assets(self):
        return dict(js=["js/tuyasmartplug.js"], css=["css/tuyasmartplug.css"])

    # ~~ TemplatePlugin mixin

    def get_template_configs(self):
        return [
            dict(type="navbar", custom_bindings=True),
            dict(type="settings", custom_bindings=True),
        ]

    # ~~ SimpleApiPlugin mixin

    def turn_on(self, pluglabel, _from_link=False):
        self._logger.info("Turning on '%s'.", pluglabel)
        if self.is_turned_on(pluglabel=pluglabel):
            self._logger.info("Plug '%s' already on.", pluglabel)
            self._plugin_manager.send_plugin_message(
                self._identifier, dict(currentState="on", label=pluglabel)
            )
            return
        plug = self.plug_search(
            self._settings.get(["arrSmartplugs"]), "label", pluglabel
        )
        self._logger.debug("Plug config: %s", plug)
        if plug["useCountdownRules"]:
            chk = self.sendCommand(
                "countdown", plug["label"], int(plug["countdownOnDelay"])
            )
        else:
            chk = self.sendCommand("on", plug["label"])

        if chk is not False:
            self.check_status(plug["label"], chk)
            if plug["autoConnect"]:
                c = threading.Timer(
                    int(plug["autoConnectDelay"]), self._printer.connect
                )
                c.start()
            if plug["sysCmdOn"]:
                t = threading.Timer(
                    int(plug["sysCmdOnDelay"]), os.system, args=[plug["sysRunCmdOn"]]
                )
                t.start()
        else:
            self._plugin_manager.send_plugin_message(
                self._identifier, dict(currentState="unknown", label=pluglabel)
            )

        if not _from_link:
            self._trigger_linked(plug, "on")

    def turn_off(self, pluglabel, _from_link=False):
        self._logger.info("Turning off '%s'.", pluglabel)
        if not self.is_turned_on(pluglabel=pluglabel):
            self._logger.info("Plug '%s' already off.", pluglabel)
            self._plugin_manager.send_plugin_message(
                self._identifier, dict(currentState="off", label=pluglabel)
            )
            return
        plug = self.plug_search(
            self._settings.get(["arrSmartplugs"]), "label", pluglabel
        )
        self._logger.debug("Plug config: %s", plug)
        if plug["useCountdownRules"]:
            chk = self.sendCommand(
                "countdown", plug["label"], int(plug["countdownOffDelay"])
            )

        if plug["sysCmdOff"]:
            t = threading.Timer(
                int(plug["sysCmdOffDelay"]), os.system, args=[plug["sysRunCmdOff"]]
            )
            t.start()
        if plug["autoDisconnect"]:
            self._printer.disconnect()
            time.sleep(int(plug["autoDisconnectDelay"]))

        if not plug["useCountdownRules"]:
            chk = self.sendCommand("off", plug["label"])

        if chk is not False:
            self.check_status(plug["label"], chk)
        else:
            self._plugin_manager.send_plugin_message(
                self._identifier, dict(currentState="unknown", label=pluglabel)
            )

        if not _from_link:
            self._trigger_linked(plug, "off")

    def _trigger_linked(self, plug, action):
        linked = plug.get("linkedPlugs", "")
        if not linked:
            return
        for label in linked.split(","):
            label = label.strip()
            if not label:
                continue
            target = self.plug_search(
                self._settings.get(["arrSmartplugs"]), "label", label
            )
            if not target:
                self._logger.warning("Linked plug '%s' not found.", label)
                continue
            self._logger.info("Linked: %s '%s'.", action, label)
            if action == "on":
                threading.Thread(target=self.turn_on, args=[label], kwargs={"_from_link": True}).start()
            else:
                threading.Thread(target=self.turn_off, args=[label], kwargs={"_from_link": True}).start()

    def check_status(self, pluglabel, resp=None):
        self._logger.debug("Checking status of '%s'.", pluglabel)
        if pluglabel != "":
            response = resp or self.sendCommand("info", pluglabel)
            if response is False:
                self._logger.warning("Plug '%s': status check FAILED.", pluglabel)
                self._plugin_manager.send_plugin_message(
                    self._identifier, dict(currentState="unknown", label=pluglabel)
                )
            else:
                state = "on" if self.is_turned_on(response, pluglabel) else "off"
                self._logger.info(
                    "Plug '%s' is %s. (dps: %s)",
                    pluglabel,
                    state.upper(),
                    response.get("dps", {}),
                )
                self._plugin_manager.send_plugin_message(
                    self._identifier,
                    dict(currentState=state, label=pluglabel),
                )

    def is_turned_on(self, data=None, pluglabel=None):
        if data is None and pluglabel:
            data = self.sendCommand("info", pluglabel)
        plug = self.plug_search(
            self._settings.get(["arrSmartplugs"]), "label", pluglabel
        )
        if not data or not plug:
            return False
        primary_slot = self._get_slots(plug)[0]
        return data.get("dps", {}).get(str(primary_slot))

    def is_api_protected(self):
        return True

    def get_api_commands(self):
        return dict(turnOn=["label"], turnOff=["label"], checkStatus=["label"])

    def on_api_command(self, command, data):
        self._logger.info("API command: %s %s", command, data.get("label", ""))
        if command == "turnOn":
            self.turn_on("{label}".format(**data))
        elif command == "turnOff":
            self.turn_off("{label}".format(**data))
        elif command == "checkStatus":
            self.check_status("{label}".format(**data))

    # ~~ Utilities

    @staticmethod
    def _get_slots(plug):
        raw = str(plug.get("slot", 1))
        slots = []
        for part in raw.split(","):
            part = part.strip()
            if "-" in part:
                start, end = part.split("-", 1)
                slots.extend(range(int(start), int(end) + 1))
            else:
                slots.append(int(part))
        return slots

    def plug_search(self, lst, key, value):
        for item in lst:
            if item[key] == value:
                return item

    def _get_protocol_version(self, plug):
        version_str = plug.get("protocolVersion", "auto")
        if version_str == "auto":
            return None
        try:
            version = float(version_str)
        except (ValueError, TypeError):
            return None
        if version not in VALID_VERSIONS:
            return None
        return version

    def _make_device(self, plug, version):
        device = tinytuya.OutletDevice(
            dev_id=plug["id"],
            address=plug["ip"],
            local_key=plug["localKey"],
            version=version,
        )
        device.set_socketTimeout(5)
        device.set_socketRetryLimit(2)
        device.set_socketRetryDelay(1)
        return device

    def _auto_detect_version(self, plug):
        self._logger.info(
            "Auto-detecting protocol for '%s' at %s...", plug["label"], plug["ip"]
        )
        for ver in AUTO_DETECT_ORDER:
            self._logger.debug("  Trying v%.1f...", ver)
            device = self._make_device(plug, ver)
            result = device.status()
            if isinstance(result, dict) and "dps" in result:
                self._logger.info(
                    "Plug '%s': detected protocol v%.1f.", plug["label"], ver
                )
                self._save_detected_version(plug["label"], ver)
                return ver
            self._logger.debug("  v%.1f failed: %s", ver, result)
        self._logger.warning(
            "Plug '%s': auto-detection failed. Check Local Key.", plug["label"]
        )
        return None

    def _save_detected_version(self, label, version):
        plugs = self._settings.get(["arrSmartplugs"])
        for plug in plugs:
            if plug.get("label") == label:
                plug["protocolVersion"] = str(version)
                break
        self._settings.set(["arrSmartplugs"], plugs)
        self._settings.save()
        self._logger.info(
            "Saved detected protocol v%.1f for '%s' to settings.", version, label
        )

    def _exec_device_command(self, device, cmd, plug, args):
        commands = {
            "info": ("status", None),
            "on": ("set_status", True),
            "off": ("set_status", False),
            "countdown": ("set_timer", None),
        }
        command, arg = commands[cmd]
        func = getattr(device, command, None)
        if not func:
            self._logger.error("No such command '%s'", command)
            return False

        slots = self._get_slots(plug)
        self._logger.debug(
            "Calling device.%s(%s)",
            command,
            ("args=%s" % args)
            if args
            else ("arg=%s, slots=%s" % (arg, slots))
            if arg is not None
            else "",
        )
        if args:
            result = func(args)
        elif arg is not None:
            for slot in slots:
                result = func(arg, slot)
        else:
            result = func()

        self._logger.debug("Command response: %s", result)

        if isinstance(result, dict) and "Error" in result:
            return result

        time.sleep(0.5)
        self._logger.debug("Fetching status after command...")
        ret = device.status()
        self._logger.debug("Status response: %s", ret)

        if isinstance(ret, dict) and "Error" in ret:
            return ret

        return ret

    def sendCommand(self, cmd, pluglabel, args=None, tries=1):
        self._logger.info("Sending '%s' to '%s' (attempt %d/3).", cmd, pluglabel, tries)
        plug = self.plug_search(
            self._settings.get(["arrSmartplugs"]), "label", pluglabel
        )
        if not plug:
            self._logger.error("Plug '%s' not found in settings!", pluglabel)
            return False

        version = self._get_protocol_version(plug)
        if version is None:
            version = self._auto_detect_version(plug)
            if version is None:
                return False

        self._logger.debug(
            "Connecting: ip=%s, id=%s, slots=%s, v%.1f",
            plug["ip"],
            plug["id"],
            self._get_slots(plug),
            version,
        )

        device = self._make_device(plug, version)

        try:
            ret = self._exec_device_command(device, cmd, plug, args)

            if ret is False:
                return False

            if isinstance(ret, dict) and "Error" in ret:
                self._logger.warning(
                    "Plug '%s': '%s' error: %s (code %s).",
                    pluglabel,
                    cmd,
                    ret.get("Error"),
                    ret.get("Err"),
                )
                if tries <= 3:
                    self._logger.debug("Retrying (%d/3)...", tries)
                    time.sleep(1)
                    return self.sendCommand(cmd, pluglabel, args, tries + 1)
                self._logger.error(
                    "Plug '%s': gave up after %d attempts.", pluglabel, tries
                )
                return False

            return ret
        except Exception as e:
            self._logger.error(
                "Plug '%s': '%s' failed (ip=%s, v%.1f): %s [%s]",
                pluglabel,
                cmd,
                plug["ip"],
                version,
                e,
                type(e).__name__,
            )
            if tries <= 3:
                self._logger.debug("Retrying (%d/3)...", tries)
                time.sleep(1)
                return self.sendCommand(cmd, pluglabel, args, tries + 1)
            self._logger.error(
                "Plug '%s': gave up after %d attempts.", pluglabel, tries
            )
            return False

    # ~~ Persistent listener for real-time state updates

    def _start_listeners(self):
        self._listener_stop.clear()
        for plug in self._settings.get(["arrSmartplugs"]):
            label = plug.get("label", "")
            if label and plug.get("ip") and plug.get("localKey"):
                if (
                    label not in self._listeners
                    or not self._listeners[label].is_alive()
                ):
                    t = threading.Thread(
                        target=self._listener_loop,
                        args=(dict(plug),),
                        daemon=True,
                        name="tuya-listener-%s" % label,
                    )
                    self._listeners[label] = t
                    t.start()
                    self._logger.info("Started listener for '%s'.", label)

    def _stop_listeners(self):
        self._listener_stop.set()
        self._listeners.clear()
        self._logger.info("Stopped all listeners.")

    def _restart_listeners(self):
        self._stop_listeners()
        time.sleep(1)
        self._start_listeners()

    def _listener_loop(self, plug):
        label = plug["label"]
        slot = str(self._get_slots(plug)[0])
        reconnect_delay = 5
        last_state = None

        while not self._listener_stop.is_set():
            version = self._get_protocol_version(plug)
            if version is None:
                version = self._auto_detect_version(plug)
                if version is None:
                    self._logger.warning(
                        "Listener '%s': cannot detect version, retrying in 30s.", label
                    )
                    if self._listener_stop.wait(30):
                        return
                    continue

            try:
                device = self._make_device(plug, version)
                device.set_socketPersistent(True)
                device.set_socketTimeout(10)

                initial = device.status()
                if isinstance(initial, dict) and "dps" in initial:
                    last_state = bool(initial["dps"].get(slot))
                    state_str = "on" if last_state else "off"
                    self._logger.info(
                        "Listener '%s': connected, state=%s.", label, state_str
                    )
                    self._plugin_manager.send_plugin_message(
                        self._identifier,
                        dict(currentState=state_str, label=label),
                    )
                    reconnect_delay = 5
                else:
                    self._logger.warning(
                        "Listener '%s': initial status failed: %s", label, initial
                    )
                    device.close()
                    if self._listener_stop.wait(reconnect_delay):
                        return
                    reconnect_delay = min(reconnect_delay * 2, 60)
                    continue

                device.set_sendWait(0)
                heartbeat_interval = 9

                while not self._listener_stop.is_set():
                    data = device.receive()
                    self._logger.debug("Listener '%s': received %s", label, data)

                    if data and isinstance(data, dict):
                        dps = data.get("dps") or data.get("data", {}).get("dps")
                        if dps and slot in dps:
                            new_state = bool(dps[slot])
                            if new_state != last_state:
                                last_state = new_state
                                state_str = "on" if new_state else "off"
                                self._logger.info(
                                    "Listener '%s': state changed to %s.",
                                    label,
                                    state_str.upper(),
                                )
                                self._plugin_manager.send_plugin_message(
                                    self._identifier,
                                    dict(currentState=state_str, label=label),
                                )

                    device.heartbeat()
                    if self._listener_stop.wait(heartbeat_interval):
                        device.close()
                        return

            except Exception as e:
                self._logger.warning(
                    "Listener '%s': connection lost: %s [%s]. Reconnecting in %ds.",
                    label,
                    e,
                    type(e).__name__,
                    reconnect_delay,
                )
                if self._listener_stop.wait(reconnect_delay):
                    return
                reconnect_delay = min(reconnect_delay * 2, 60)

    # ~~ Gcode processing hook

    def gcode_turn_off(self, plug):
        if plug["warnPrinting"] and self._printer.is_printing():
            self._logger.info(
                "Not powering off %s because printer is printing.", plug["label"]
            )
        else:
            self.turn_off(plug["label"])

    def _find_plug_by_name(self, name):
        plug = self.plug_search(self._settings.get(["arrSmartplugs"]), "ip", name)
        if not plug:
            plugs = self._settings.get(["arrSmartplugs"])
            for item in plugs:
                if item["label"].upper() == name.upper():
                    plug = item
                    break
        return plug

    def _gcode_power(self, cmd_name, name, action):
        self._logger.debug("GCODE %s: %s '%s'.", cmd_name, action, name)
        plug = self._find_plug_by_name(name)
        if not plug or not plug["gcodeEnabled"]:
            return
        if action == "on":
            delay = int(plug["gcodeOnDelay"])
            t = threading.Timer(delay, self.turn_on, args=[plug["label"]])
        else:
            delay = int(plug["gcodeOffDelay"])
            t = threading.Timer(delay, self.gcode_turn_off, args=[plug])
        t.start()

    _GCODE_TRIGGERS = [
        ("M80", "on"),
        ("M81", "off"),
        ("G4 P1", "on"),
        ("G4 P2", "off"),
    ]

    def processGCODE(self, comm_instance, phase, cmd, cmd_type, gcode, *args, **kwargs):
        if not gcode:
            return
        for prefix, action in self._GCODE_TRIGGERS:
            if cmd.startswith(prefix):
                name = cmd[len(prefix) :].strip()
                self._gcode_power(prefix, name, action)
                return None

    # ~~ Softwareupdate hook

    def get_update_information(self):
        return dict(
            tuyasmartplug=dict(
                displayName="Tuya Smartplug",
                displayVersion=self._plugin_version,
                type="github_release",
                user="ziirish",
                repo="OctoPrint-TuyaSmartplug",
                current=self._plugin_version,
                pip="https://github.com/ziirish/OctoPrint-TuyaSmartplug/archive/{target_version}.zip",
            )
        )


__plugin_name__ = "Tuya Smartplug"
__plugin_version__ = "1.0.0"
__plugin_pythoncompat__ = ">=3,<4"


def __plugin_load__():
    global __plugin_implementation__
    __plugin_implementation__ = tuyasmartplugPlugin()

    global __plugin_hooks__
    __plugin_hooks__ = {
        "octoprint.comm.protocol.gcode.queuing": __plugin_implementation__.processGCODE,
        "octoprint.plugin.softwareupdate.check_config": __plugin_implementation__.get_update_information,
    }
