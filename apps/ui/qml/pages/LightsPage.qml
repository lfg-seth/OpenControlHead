import QtQuick 2.15
import QtQuick.Controls 2.15

Item {
    id: lightsPage
    property var rootWindow

    onRootWindowChanged: {
        if (!rootWindow)
            return;

        rootWindow.setTopBar([
            {
                label: "INTERIOR",
                onClick: function () {}
            },
            {
                label: "SCENES",
                onClick: function () {}
            },
            {
                label: "<----",
                onClick: function () {}
            },
            {
                label: "<---->",
                onClick: function () {}
            },
            {
                label: "---->",
                onClick: function () {}
            }
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
            anchors.margins: 10
            spacing: 10

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
                    id: labelsColumn
                    anchors.left: parent.left
                    anchors.top: parent.top
                    spacing: 10
                    anchors.margins: 20
                    width: parent.width - 100

                    Row {
                        width: parent.width
                        spacing: 40

                        Text {
                            text: "P1 FRONT LIGHTS"
                            font.pixelSize: 30
                            color: "#FFFFFF"
                            padding: 3
                        }
                        Text {
                            text: "HIGH"
                            font.pixelSize: 30
                            color: '#00FFFF'
                            padding: 3
                        }
                    }

                    Row {
                        width: parent.width
                        spacing: 30

                        Text {
                            text: "P2 DITCH LIGHTS"
                            font.pixelSize: 30
                            color: "#FFFFFF"
                            padding: 3
                        }
                        Text {
                            text: "HIGH"
                            font.pixelSize: 30
                            color: '#00FFFF'
                            padding: 3
                        }
                    }

                    Row {
                        width: parent.width
                        spacing: 30

                        Text {
                            text: "P3 REAR LIGHTS"
                            font.pixelSize: 30
                            color: "#FFFFFF"
                            padding: 3
                        }
                        Text {
                            text: "HIGH"
                            font.pixelSize: 30
                            color: '#00FFFF'
                            padding: 3
                        }
                    }

                    Row {
                        width: parent.width
                        spacing: 30

                        Text {
                            text: "P4 ROCK LIGHTS"
                            font.pixelSize: 30
                            color: "#FFFFFF"
                            padding: 3
                        }
                        Text {
                            text: "HIGH"
                            font.pixelSize: 30
                            color: '#00FFFF'
                            padding: 3
                        }
                    }

                    Row {
                        width: parent.width
                        spacing: 30

                        Text {
                            text: "P5 EMERGENCY LIGHTS"
                            font.pixelSize: 30
                            color: "#FFFFFF"
                            padding: 3
                        }
                        Text {
                            text: "HIGH"
                            font.pixelSize: 30
                            color: '#00FFFF'
                            padding: 3
                        }
                    }
                }
            }
        }
    }
}
