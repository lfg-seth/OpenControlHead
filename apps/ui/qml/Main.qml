import QtQuick 2.15
import QtQuick.Window 2.15
import QtQuick.Layouts 1.15

Window {
    id: root
    width: 800
    height: 480
    visible: true
    color: "#000000"
    title: "o9 Control Head"

    // Page IDs (single source of truth)
    readonly property string page_HOME: "HomePage"
    readonly property string page_LIGHTS: "LightsPage"
    readonly property string page_AIR: "AirPage"
    readonly property string page_DRIVETRAIN: "DrivetrainPage"
    readonly property string page_WEATHER: "WeatherPage"
    readonly property string page_VEHICLE: "VehiclePage"
    readonly property string page_RADIO: "RadioPage"
    readonly property string page_POWER: "PowerPage"
    readonly property string page_CLIMATE: "ClimatePage"
    readonly property string page_NETWORK: "NetworkPage"
    readonly property string page_SETTINGS: "SettingsPage"
    readonly property string page_DEBUG: "DebugPage"
    readonly property string page_TRIP: "TripPage"
    readonly property string page_SECURITY: "SecurityPage"
    readonly property string page_SYSTEM: "SystemPage"
    readonly property string page_WINCH: "WinchPage"
    readonly property string page_SUSPENSION: "SuspensionPage"
    // add more pages as needed...

    // Current page
    property string currentPage: page_HOME

    // Softkey paging config
    readonly property int itemsPerPage: 4      // 4 softkeys + 1 MORE
    property int currentMenuPage: 0

    // Menu definition: order = how they appear as you page
    property var menuItems: [
        {
            label: "LIGHTS",
            pageId: page_LIGHTS
        },
        {
            label: "AIR",
            pageId: page_AIR
        },
        {
            label: "DRIVETRAIN",
            pageId: page_DRIVETRAIN
        },
        {
            label: "WEATHER",
            pageId: page_WEATHER
        },
        {
            label: "VEHICLE",
            pageId: page_VEHICLE
        },
        {
            label: "RADIO",
            pageId: page_RADIO
        },
        {
            label: "POWER",
            pageId: page_POWER
        },
        {
            label: "CLIMATE",
            pageId: page_CLIMATE
        },
        {
            label: "NETWORK",
            pageId: page_NETWORK
        },
        {
            label: "SETTINGS",
            pageId: page_SETTINGS
        },
        {
            label: "DEBUG",
            pageId: page_DEBUG
        },
        {
            label: "TRIP",
            pageId: page_TRIP
        },
        {
            label: "SECURITY",
            pageId: page_SECURITY
        },
        {
            label: "SYSTEM",
            pageId: page_SYSTEM
        },
        {
            label: "WINCH",
            pageId: page_WINCH
        },
        {
            label: "SUSPENSION",
            pageId: page_SUSPENSION
        }

        // add more: { label: "PUMPS", pageId: page_PUMPS }, etc.
        ,
    ]

    readonly property int menuPageCount: Math.max(1, Math.ceil(menuItems.length / itemsPerPage))

    // Top softkeys: 5 slots (page-specific)
    // Each entry: { label: "TEXT", onClick: function() { ... } }
    property var topButtons: [
        {
            "label": "VEHICLE",
            "onClick": function () {
                setPage(page_VEHICLE);
            }
        },
        {
            "label": "RADIO",
            "onClick": function () {
                setPage(page_RADIO);
            }
        },
        {
            "label": "POWER",
            "onClick": function () {
                setPage(page_POWER);
            }
        },
        {
            "label": "CLIMATE",
            "onClick": function () {
                setPage(page_CLIMATE);
            }
        },
        {
            "label": "NETWORK",
            "onClick": function () {
                setPage(page_NETWORK);
            }
        }
    ]

    function setTopBar(buttons) {
        // Normalize into exactly 5 entries
        var arr = [];
        for (var i = 0; i < 5; ++i) {
            var b = (buttons && buttons[i]) || {};
            arr.push({
                label: b.label || "",
                onClick: b.onClick || null
            });
        }
        topButtons = arr;
    }

    // Global typography/colors
    property color textPrimary: "#E6E6E6"
    property color textBlue: "#00FFFF"
    property color textGreen: "#00FF5F"
    property color accent: "#00FFD1"
    property int gutterH: 70
    property int bottom_gutterH: 40

    Rectangle {
        anchors.fill: parent
        color: "#000"
    }

    function setPage(pageId) {
        if (!pageId)
            return;
        if (currentPage === pageId)
            return;
        console.log("Setting page:", pageId);
        currentPage = pageId;
    }

    function menuIndexForSlot(slotIndex) {
        return currentMenuPage * itemsPerPage + slotIndex;
    }

    function menuItemForSlot(slotIndex) {
        var i = menuIndexForSlot(slotIndex);
        return (i >= 0 && i < menuItems.length) ? menuItems[i] : null;
    }

    function activateMenuSlot(slotIndex) {
        var item = menuItemForSlot(slotIndex);
        if (item && item.pageId) {
            setPage(item.pageId);
        } else {
            console.log("No menu item for slot", slotIndex, "on page", currentMenuPage);
        }
    }

    function nextMenuPage() {
        if (menuPageCount <= 1)
            return;
        currentMenuPage = (currentMenuPage + 1) % menuPageCount;
        console.log("Menu page ->", currentMenuPage + 1, "/", menuPageCount);
    }

    // Hardware → navigation mapping
    Connections {
        target: Bridge
        function onPicoButton(name, pressed) {
            if (!pressed)
                return;

            console.log("PicoButton:", name, "pressed");

            switch (name) {
            case "COMPUTER":      // your Home key
                setPage(page_HOME);
                break;
            case "B_ROW1":        // bottom softkey 1
                activateMenuSlot(0);
                break;
            case "B_ROW2":        // bottom softkey 2
                activateMenuSlot(1);
                break;
            case "B_ROW3":        // bottom softkey 3
                activateMenuSlot(2);
                break;
            case "B_ROW4":        // bottom softkey 4
                activateMenuSlot(3);
                break;
            case "B_ROW5":        // bottom softkey 5 = MORE
                nextMenuPage();
                break;
            default:
                break;
            }
        }
    }

    // Top softkey label gutter (static for now)
    RowLayout {
        id: topGutter
        anchors.top: parent.top
        anchors.left: parent.left
        anchors.right: parent.right
        height: root.gutterH
        spacing: 0

        Repeater {
            model: 5
            delegate: Rectangle {
                Layout.fillWidth: true
                height: root.gutterH
                color: "#000"
                border.color: "#101010"
                border.width: 1

                property var btn: index < topButtons.length ? topButtons[index] : ({})
                readonly property bool hasAction: btn && btn.onClick

                Text {
                    font.family: "Oxygen Mono"
                    anchors.centerIn: parent
                    text: btn.label || ""
                    color: hasAction ? textPrimary : "#444444"
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                    wrapMode: Text.WordWrap
                    maximumLineCount: 2
                    width: parent.width - 10  // small padding to prevent clipping

                    // Font size logic
                    font.pixelSize: {
                        if (!btn.label)
                            return 26;
                        if (btn.label.indexOf("\n") !== -1)
                            return 22;       // has newline
                        if (btn.label.length > 9)
                            return 22;                 // long text
                        return 26;                                           // default
                    }
                }

                MouseArea {
                    anchors.fill: parent
                    enabled: hasAction
                    onClicked: {
                        if (btn.onClick)
                            btn.onClick();
                    }
                }
            }
        }
    }

    // Status Bar
    // In your Window { ... }

    property real statusVoltage: 12.443
    property int statusPingMs: 60
    property int statusMbps: 83
    property int statusTempF: 72
    property int statusCurrentA: -13
    property string statusDriveMode: "2WD"

    // Status bar with vehicle info
    RowLayout {
        id: statusBar
        anchors.top: topGutter.bottom
        anchors.left: parent.left
        anchors.right: parent.right
        height: root.gutterH / 2

        Rectangle {
            Layout.fillWidth: true
            height: statusBar.height
            color: "#101010"

            Row {
                id: statusRow
                anchors.centerIn: parent
                spacing: 22

                // 12.4V
                Row {
                    spacing: 4
                    Text {
                        font.family: "Oxygen Mono"
                        text: statusVoltage.toFixed(1)
                        color: "#00FF5F"
                        font.pixelSize: 24
                    }
                    Text {
                        font.family: "Oxygen Mono"
                        text: "V"
                        color: textPrimary
                        font.pixelSize: 24
                    }
                }

                // 60ms
                Row {
                    spacing: 4
                    Text {
                        text: statusPingMs
                        color: "#00FF5F"
                        font.pixelSize: 24
                        font.family: "Oxygen Mono"
                    }
                    Text {
                        text: "ms"
                        color: textPrimary
                        font.pixelSize: 24
                        font.family: "Oxygen Mono"
                    }
                }

                // 83mbps
                Row {
                    spacing: 4
                    Text {
                        text: statusMbps
                        color: "#00FF5F"
                        font.pixelSize: 24
                        font.family: "Oxygen Mono"
                    }
                    Text {
                        text: "mbps"
                        color: textPrimary
                        font.pixelSize: 24
                        font.family: "Oxygen Mono"
                    }
                }

                // 72°F
                Row {
                    spacing: 4
                    Text {
                        text: statusTempF
                        color: "#00FF5F"
                        font.pixelSize: 24
                        font.family: "Oxygen Mono"
                    }
                    Text {
                        text: "°F"
                        color: textPrimary
                        font.pixelSize: 24
                        font.family: "Oxygen Mono"
                    }
                }

                // -13A (orange for current)
                Row {
                    spacing: 4
                    Text {
                        text: statusCurrentA
                        color: "#FFA500"
                        font.pixelSize: 24
                        font.family: "Oxygen Mono"
                    }
                    Text {
                        text: "A"
                        color: textPrimary
                        font.pixelSize: 24
                        font.family: "Oxygen Mono"
                    }
                }

                // 2WD
                Text {
                    text: statusDriveMode
                    color: "#00FFFF"
                    font.pixelSize: 24
                    font.family: "Oxygen Mono"
                }
            }
        }
    }

    // Dynamic page container
    Loader {
        id: pageLoader
        anchors.top: statusBar.bottom
        anchors.bottom: bottomGutter.top
        anchors.left: parent.left
        anchors.right: parent.right
        source: "pages/" + currentPage + ".qml"

        onLoaded: {
            if (item && item.hasOwnProperty("rootWindow")) {
                item.rootWindow = root;
            }
        }
    }
    // Bottom softkey label gutter driven by menuItems + MORE
    RowLayout {
        id: bottomGutter
        anchors.bottom: parent.bottom
        anchors.left: parent.left
        anchors.right: parent.right
        height: root.bottom_gutterH
        spacing: 0

        // Slots 0-3 use menuItems
        Repeater {
            model: 4
            delegate: Rectangle {
                Layout.fillWidth: true
                height: root.bottom_gutterH
                color: "#000"
                border.color: "#101010"
                border.width: 1

                property int slotIndex: index
                property var item: menuItemForSlot(slotIndex)

                Text {
                    font.family: "Oxygen Mono"
                    anchors.centerIn: parent
                    text: item ? item.label : ""
                    color: item && currentPage === item.pageId ? textBlue : textPrimary
                    font.pixelSize: item && item.label.length > 9 ? 22 : 26
                }
                MouseArea {
                    anchors.fill: parent
                    onClicked: {
                        console.log("Clicked ", item.label, " button");
                        activateMenuSlot(slotIndex);
                    }
                }
            }
        }

        // Slot 4 = MORE (page cycling)
        Rectangle {
            Layout.fillWidth: true
            height: root.bottom_gutterH
            color: "#000"
            border.color: "#101010"
            border.width: 1

            Text {
                font.family: "Oxygen Mono"
                anchors.centerIn: parent
                text: "MORE"
                color: menuPageCount > 1 ? textPrimary : "#555555"
                font.pixelSize: 26
            }
            MouseArea {
                anchors.fill: parent
                onClicked: {
                    console.log("Clicked MORE button");
                    nextMenuPage();
                }
            }
        }
    }
}
