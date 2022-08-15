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
    document.querySelectorAll('div[class="dressing-room-loader"]')
        .forEach(value => {
            value.style.display = "block";
        });
}

function showButtons() {
    window.top.document.querySelectorAll('div[class="dressing-room-loader"]')
        .forEach(value => {
            value.style.display = "none";
        });
}

function showDay(day) {
    document.querySelectorAll("tr.day-collapsed." + day)
        .forEach(value => {
            value.style.display = "none";
        });
    document.querySelectorAll("tr.day-contents." + day)
        .forEach(value => {
            value.style.display = "table-row";
        });
}

function hideDay(day) {
    document.querySelectorAll("tr.day-contents." + day)
        .forEach(value => {
            value.style.display = "none";
        });
    document.querySelectorAll("tr.day-collapsed." + day)
        .forEach(value => {
            value.style.display = "table-row";
        });
}

function showCurrentDay() {
    const d = new Date();
    day = d.getDay();
    hours = d.getHours();
    if (hours < 6) {
        // Same night is regarded same day
        day--;
        if (day == -1) {
            day = 0;
        }
    }
    console.log(day);

    const dayToText = {
        4: "donderdag",
        5: "vrijdag",
        6: "zaterdag",
        7: "zondag"
    };
    if (day in dayToText) {
        showDay(dayToText[day]);
    } else {
        showDay("donderdag");
    }
}
