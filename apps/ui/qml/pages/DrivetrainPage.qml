// pages/DrivetrainPage.qml
import QtQuick 2.15
import QtQuick.Controls 2.15

Item {
    id: drivetrainPage
    anchors.fill: parent
    // Injected by main.qml Loader.onLoaded
    property var rootWindow

    // When rootWindow is set, configure the top bar
    onRootWindowChanged: {
        if (!rootWindow)
            return;

        rootWindow.setTopBar([
            {
                "label": "A-TRAC",
                "onClick": function () {
                }
            },
            {
                "label": "DOWNHILL ASSIST",
                "onClick": function () {
                }
            },
            {
                "label": "LOCK\nFRONT DIFF",
                "onClick": function () {
                }
            },
            {
                "label": "LOCK\nREAR DIFF",
                "onClick": function () {
                }
            },
            {
                "label": "SHIFT\n4HI",
                "onClick": function () {
                }
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
            text: "DRIVETRAIN"
            color: "#E6E6E6"
            font.pixelSize: 36
        }
    }
}
