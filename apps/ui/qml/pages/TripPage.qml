// pages/TripPage.qml
import QtQuick 2.15
import QtQuick.Controls 2.15

Item {
    id: tripPage
    anchors.fill: parent
    // Injected by main.qml Loader.onLoaded
    property var rootWindow

    // When rootWindow is set, configure the top bar
    onRootWindowChanged: {
        if (!rootWindow)
            return;

        rootWindow.setTopBar([
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
            text: "TRIP"
            color: "#E6E6E6"
            font.pixelSize: 36
        }
    }
}
