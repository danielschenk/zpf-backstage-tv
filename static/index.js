function updateDressingRoom(actKey, roomNumber) {
    fetch("dressing_room/" + actKey, {
        "method": "PUT",
        "body": roomNumber
    })
}
