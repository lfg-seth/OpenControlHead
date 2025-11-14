import QtQuick 2.15
import QtQuick.Controls 2.15

Item {
    id: lightsPage
    property var rootWindow

    onRootWindowChanged: {
        if (!rootWindow)
            return;

        rootWindow.setTopBar([
            { label: "INTERIOR", onClick: function () {} },
            { label: "SCENES",   onClick: function () {} },
            { label: "<----",    onClick: function () {} },
            { label: "<---->",   onClick: function () {} },
            { label: "---->",    onClick: function () {} }
        ]);
    }

    Rectangle {
        id: contentBg
        anchors.fill: parent
        color: "#0A0A0A"
        radius: 8
        border.color: "#141414"

        Row {
            id: contentRow
            anchors.fill: parent
            anchors.margins: 20
            spacing: 20

            Rectangle {
                id: svgPanel
                width: 300
                height: parent.height
                color: "#222222"
                radius: 8
                border.color: "#333333"

                Image {
                    anchors.centerIn: parent
                    source: "qrc:/assets/4runner-02.svg"
                    fillMode: Image.PreserveAspectFit
                    height: parent.height * .8
                    transformOrigin: Item.Center
                }
            }

            Rectangle {
                id: controlsPanel
                anchors.left: svgPanel.right
                anchors.right: parent.right
                anchors.top: parent.top
                anchors.bottom: parent.bottom
                color: "#222222"
                radius: 8
                border.color: "#333333"

                Column {
                    anchors.centerIn: parent
                    spacing: 16

                    Switch {
                        id: frontLightsSwitch
                        property bool isSwitch: true
                        property string switchName: "Front Lights"
                        text: "Front Lights"
                        onToggled: {
                            // `checked` is the new state
                            Bridge.setSwitchState("Front Lights", checked)
                        }
                    }

                    // Example of a pure action button:
                    Button {
                        text: "Toggle Front Lights"
                        onClicked: Bridge.toggleSwitch("Front Lights")
                    }
                }
            }
        }
    }
}
