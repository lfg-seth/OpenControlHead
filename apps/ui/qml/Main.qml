// qml/Main.qml
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

    // Global typography/colors
    property color textPrimary: "#E6E6E6"
    property color accent: "#00FFD1"
    property int gutterH: 50
    property bool gp9Pressed: false

    Rectangle {
        anchors.fill: parent
        color: "#000"
    }

    Connections {
        target: Bridge
        function onPicoButton(name, pressed) {
            if (name === "GP9")
                gp9Pressed = pressed;
        }
    }

    // Top softkey label gutter (5 slots)
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
                Text {
                    font.family: "Oxygen Mono"
                    anchors.centerIn: parent
                    text: "F" + (index + 1)
                    color: root.textPrimary
                    font.pixelSize: 28
                }
            }
        }
    }

    // Main content
    Column {
        anchors.top: topGutter.bottom
        anchors.bottom: bottomGutter.top
        anchors.left: parent.left
        anchors.right: parent.right
        spacing: 12
        Rectangle {
            anchors.margins: 12
            anchors.fill: parent
            color: "#0A0A0A"
            radius: 8
            border.color: "#141414"
            Text {
                anchors.centerIn: parent
                text: "HOME"
                color: gp9Pressed ? root.accent : root.textPrimary
                font.pixelSize: 36
                font.letterSpacing: 2
                Behavior on color {
                    ColorAnimation {
                        duration: 120
                    }
                }
            }
        }
        Rectangle {
            id: btnIndicator
            width: 18
            height: 18
            radius: 3
            anchors.right: parent.right
            anchors.rightMargin: 16
            anchors.top: parent.top
            anchors.topMargin: 16
            color: gp9Pressed ? "#36e07f" : "#202020"
            border.color: gp9Pressed ? "#9cffc7" : "#333"
        }
    }

    // Bottom softkey label gutter (5 slots)
    RowLayout {
        id: bottomGutter
        anchors.bottom: parent.bottom
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
                Text {
                    anchors.centerIn: parent
                    text: "P" + (index + 1)
                    color: root.textPrimary
                    font.pixelSize: 18
                }
            }
        }
    }
}
