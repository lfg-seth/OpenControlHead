// pages/AirPage.qml
import QtQuick 2.15
import QtQuick.Controls 2.15

Item {
    id: airPage
    anchors.fill: parent
    // Injected by main.qml Loader.onLoaded
    property var rootWindow

    // When rootWindow is set, configure the top bar
    onRootWindowChanged: {
        if (!rootWindow)
            return;

        rootWindow.setTopBar([
            {
                "label": "INFLATE",
                "onClick": function () {}
            },
            {
                "label": "DEFLATE",
                "onClick": function () {}
            },
            {
                "label": "SET PSI",
                "onClick": function () {
                }
            },
            {
                "label": "SET TIME",
                "onClick": function () {
                }
            },
            {
                "label": "---",
                "onClick": null
            }
        ]);
    }
    Rectangle {
        anchors.fill: parent
        color: "#0A0A0A"
        radius: 8
        border.color: "#141414"

        Text {
            font.family: "Oxygen Mono"
            anchors.centerIn: parent
            text: "AIR"
            color: "#E6E6E6"
            font.pixelSize: 36
        }
    }
}
