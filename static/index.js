function setDressingRoom(actKey, roomNumber) {
    fetch("dressing_rooms/" + actKey, {
        "method": "PUT",
        "body": roomNumber
    })
}
