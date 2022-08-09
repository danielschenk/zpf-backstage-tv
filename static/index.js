function setDressingRoom(actKey, roomNumber) {
    hideButtons();
    fetch("dressing_rooms/" + actKey, {
        "method": "PUT",
        "body": roomNumber
    }).then(updateAllDressingRoomButtons);
}

function updateAllDressingRoomButtons() {
    hideButtons();
    document.querySelectorAll("button.dressing-room")
        .forEach(value => {
            value.classList.remove("selected");
            value.disabled = false;
        });

    fetch("dressing_rooms")
        .then(response => response.json())
        .then(data => {
            for(key in data) {
                let room = data[key];
                let button = document.getElementById(key + "-" + room);
                button.classList.add("selected");
                button.disabled = true;
            }

            showButtons();
        });
}

function hideButtons() {
    document.querySelectorAll('div[class="dressing-room-buttons"]')
        .forEach(value => {
            value.style.display = "none";
        });
    document.querySelectorAll('div[class="dressing-room-loader"]')
        .forEach(value => {
            value.style.display = "block";
        });
}

function showButtons() {
    window.top.document.querySelectorAll('div[class="dressing-room-buttons"]')
        .forEach(value => {
            value.style.display = "block";
        });
    window.top.document.querySelectorAll('div[class="dressing-room-loader"]')
        .forEach(value => {
            value.style.display = "none";
        });
}
