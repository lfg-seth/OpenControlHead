// pages/LightsPage.qml
import QtQuick 2.15
import QtQuick.Controls 2.15

Item {
    id: lightsPage

    // Injected by main.qml Loader.onLoaded
    property var rootWindow

    // When rootWindow is set, configure the top bar
    onRootWindowChanged: {
        if (!rootWindow)
            return;

        rootWindow.setTopBar([
            {
                label: "INTERIOR",
                onClick: function () {
                    
                }
            },
            {
                label: "SCENES",
                onClick: function () {
                // e.g. open a scenes overlay or toggle mode
                }
            },
            {
                label: "<----",
                onClick: function () {
                // send "all on" command via Bridge / whatever
                }
            },
            {
                label: "<---->",
                onClick: function () {
                // send "all off"
                }
            },
            {
                label: "---->",
                onClick: function () {
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
            text: "LIGHTS"
            color: "#E6E6E6"
            font.pixelSize: 36
        }
    }
}
