// Logs.qml
import QtQuick 2.15
import QtQuick.Controls 2.15

Item {
    id: root
    property int maxEntries: 200

    ListModel { id: logModel }

    Component.onCompleted: {
        LogBridge.logAdded.connect(function(level, origin, message) {
            
            logModel.append({
                "level": level,
                "origin": origin,
                "message": message
            })
            if (logModel.count > maxEntries)
                logModel.remove(0)
        })
    }

    ListView {
        anchors.fill: parent
        model: logModel
        delegate: Text {
            text: `[${level}] [${origin}] ${message}`
            font.family: "Oxygen Mono"
            font.pixelSize: 12
            color: level === "ERROR" || level === "CRITICAL"
                   ? "#FF5555"
                   : (level === "WARNING" ? "#FFC857" : "#E6E6E6")
        }
    }
}
