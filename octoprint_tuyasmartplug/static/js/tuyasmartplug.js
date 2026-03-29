/*
 * View model for OctoPrint-TuyaSmartplug
 *
 * Author: ziirish
 * License: AGPLv3
 */
$(function () {
    function tuyasmartplugViewModel(parameters) {
        var self = this;

        self.settings = parameters[0];
        self.loginState = parameters[1];

        self.arrSmartplugs = ko.observableArray();
        self.isPrinting = ko.observable(false);
        self.selectedPlug = ko.observable();
        self.processing = ko.observableArray([]);

        self.onBeforeBinding = function () {
            self.arrSmartplugs(self.settings.settings.plugins.tuyasmartplug.arrSmartplugs());
        };

        self.onAfterBinding = function () {
            self.checkStatuses();
        };

        self.onEventSettingsUpdated = function (payload) {
            self.arrSmartplugs(self.settings.settings.plugins.tuyasmartplug.arrSmartplugs());
        };

        self.onEventPrinterStateChanged = function (payload) {
            if (payload.state_id == "PRINTING" || payload.state_id == "PAUSED") {
                self.isPrinting(true);
            } else {
                self.isPrinting(false);
            }
        };

        self.cancelClick = function (data) {
            self.processing.remove(data.label());
        };

        self.editPlug = function (data) {
            self.selectedPlug(data);
            $("#TuyaPlugEditor").modal("show");
        };

        self.addPlug = function () {
            self.selectedPlug({
                ip: ko.observable(""),
                id: ko.observable(""),
                slot: ko.observable(1),
                localKey: ko.observable(""),
                label: ko.observable(""),
                icon: ko.observable("icon-bolt"),
                displayWarning: ko.observable(true),
                protocolVersion: ko.observable("auto"),
                warnPrinting: ko.observable(false),
                gcodeEnabled: ko.observable(false),
                gcodeOnDelay: ko.observable(0),
                gcodeOffDelay: ko.observable(0),
                autoConnect: ko.observable(true),
                autoConnectDelay: ko.observable(10.0),
                autoDisconnect: ko.observable(true),
                autoDisconnectDelay: ko.observable(0),
                sysCmdOn: ko.observable(false),
                sysRunCmdOn: ko.observable(""),
                sysCmdOnDelay: ko.observable(0),
                sysCmdOff: ko.observable(false),
                sysRunCmdOff: ko.observable(""),
                sysCmdOffDelay: ko.observable(0),
                currentState: ko.observable("unknown"),
                btnColor: ko.observable("#808080"),
                useCountdownRules: ko.observable(false),
                countdownOnDelay: ko.observable(0),
                countdownOffDelay: ko.observable(0),
                linkedPlugs: ko.observable(""),
            });
            self.settings.settings.plugins.tuyasmartplug.arrSmartplugs.push(
                self.selectedPlug()
            );
            $("#TuyaPlugEditor").modal("show");
        };

        self.removePlug = function (row) {
            self.settings.settings.plugins.tuyasmartplug.arrSmartplugs.remove(row);
        };

        self.onDataUpdaterPluginMessage = function (plugin, data) {
            if (plugin != "tuyasmartplug") {
                return;
            }

            var plug =
                ko.utils.arrayFirst(
                    self.settings.settings.plugins.tuyasmartplug.arrSmartplugs(),
                    function (item) {
                        return item.label() === data.label;
                    }
                ) || {
                    label: data.label,
                    currentState: "unknown",
                    btnColor: "#808080",
                };

            if (plug.currentState() !== data.currentState) {
                plug.currentState(data.currentState);
                if (data.currentState !== "on" && data.currentState !== "off") {
                    new PNotify({
                        title: "Tuya Smartplug Error",
                        text:
                            "Status " +
                            plug.currentState() +
                            " for " +
                            plug.ip() +
                            ". Double check IP Address/Device ID/Local Key in TuyaSmartplug Settings.",
                        type: "error",
                        hide: true,
                    });
                }
                self.settings.saveData();
            }
            self.processing.remove(data.label);
        };

        self.toggleRelay = function (data) {
            self.processing.push(data.label());
            switch (data.currentState()) {
                case "on":
                    self.turnOff(data);
                    break;
                case "off":
                    self.turnOn(data);
                    break;
                default:
                    self.checkStatus(data.label());
            }
        };

        self.turnOn = function (data) {
            self.sendTurnOn(data);
        };

        self.sendTurnOn = function (data) {
            $.ajax({
                url: API_BASEURL + "plugin/tuyasmartplug",
                type: "POST",
                dataType: "json",
                data: JSON.stringify({
                    command: "turnOn",
                    label: data.label(),
                }),
                contentType: "application/json; charset=UTF-8",
            });
        };

        self.turnOff = function (data) {
            if (
                (data.displayWarning() ||
                    (self.isPrinting() && data.warnPrinting())) &&
                !$("#tuyasmartplugWarning").is(":visible")
            ) {
                self.selectedPlug(data);
                $("#tuyasmartplugWarning").modal("show");
            } else {
                $("#tuyasmartplugWarning").modal("hide");
                self.sendTurnOff(data);
            }
        };

        self.sendTurnOff = function (data) {
            $.ajax({
                url: API_BASEURL + "plugin/tuyasmartplug",
                type: "POST",
                dataType: "json",
                data: JSON.stringify({
                    command: "turnOff",
                    label: data.label(),
                }),
                contentType: "application/json; charset=UTF-8",
            });
        };

        self.checkStatus = function (plugLabel) {
            $.ajax({
                url: API_BASEURL + "plugin/tuyasmartplug",
                type: "POST",
                dataType: "json",
                data: JSON.stringify({
                    command: "checkStatus",
                    label: plugLabel,
                }),
                contentType: "application/json; charset=UTF-8",
            }).done(function () {
                self.settings.saveData();
            });
        };

        self.checkStatuses = function () {
            ko.utils.arrayForEach(
                self.settings.settings.plugins.tuyasmartplug.arrSmartplugs(),
                function (item) {
                    if (item.label() !== "") {
                        self.checkStatus(item.label());
                    }
                }
            );
            if (self.settings.settings.plugins.tuyasmartplug.statusMonitor() === "polling") {
                setTimeout(function () {
                    self.checkStatuses();
                }, parseInt(self.settings.settings.plugins.tuyasmartplug.pollingInterval(), 10) * 60000);
            }
        };
    }

    OCTOPRINT_VIEWMODELS.push([
        tuyasmartplugViewModel,
        ["settingsViewModel", "loginStateViewModel"],
        ["#navbar_plugin_tuyasmartplug", "#settings_plugin_tuyasmartplug"],
    ]);
});
