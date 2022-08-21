function setDressingRoom(actKey, roomNumber) {
    hideButtons();
    fetch("itinerary/" + actKey + "/dressing_room", {
        "method": "PUT",
        "body": roomNumber
    }).then(response => {
        if (response.ok) {
            updateAllDressingRoomButtons();
        } else {
            handleSetDressingRoomError();
        }
    }, handleSetDressingRoomError);
}

function handleSetDressingRoomError() {
    window.alert("Failed to update dressing room");
    showButtons();
}

function updateAllDressingRoomButtons() {
    hideButtons();

    fetch("itinerary")
        .then(response => response.json(), () => {
            window.alert("Failed to fetch dressing rooms");
            return Promise.reject(Error("Failed to fetch dressing rooms"));
        })
        .then(data => {
            document.querySelectorAll("button.dressing-room")
                .forEach(value => {
                    console.log(value);
                    value.classList.remove("selected");
                    value.disabled = false;
                });
            for(key in data) {
                let room = data[key]["dressing_room"];
                let button = document.getElementById(key + "-" + room);
                if (button == null) {
                    console.warn("button for act " + key + " was not found");
                    continue;
                }
                button.classList.add("selected");
                button.disabled = true;
            }

            showButtons();
        }, () => {
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

let utcOverrideValue = -1;

function updateShowtimeAnnotations() {
    let utc;
    if (utcOverrideValue > -1) {
        utc = utcOverrideValue;
    } else {
        utc = new Date().getTime() / 1000;
    }

    document.querySelectorAll("li.showtime")
        .forEach(value => {
            value.classList.remove("started", "over", "almost-starting", "almost-ending");
            Array.from(value.getElementsByClassName("showtime-annotation"))
                .forEach(value => {
                    value.classList.remove("visible");
                });

            let start = parseInt(value.getAttribute("start"));
            let end = parseInt(value.getAttribute("end"));

            const warningSeconds = 5 * 60;
            let secondsLeft = -1;
            if (utc >= start && utc <= end) {
                value.classList.add("started");
                value.getElementsByClassName("started")[0].classList.add("visible");

                if (end - utc <= warningSeconds) {
                    value.classList.add("almost-ending");
                    value.getElementsByClassName("almost-ending")[0].classList.add("visible");
                    secondsLeft = end - utc;
                }
            } else if (utc > end) {
                value.classList.add("over");
            } else if (start - utc <= warningSeconds) {
                value.classList.add("almost-starting");
                value.getElementsByClassName("almost-starting")[0].classList.add("visible");
                secondsLeft = start - utc;
            }

            Array.from(value.getElementsByClassName("time-left-value"))
                .forEach(value => {
                    if (secondsLeft > 60) {
                        value.textContent = Math.floor(secondsLeft / 60) + " min.";
                    } else {
                        value.textContent = secondsLeft + " sec.";
                    }
                });
        });
}

function overrideUtc() {
    utcOverrideValue = parseInt(document.getElementById("utc").value);
    updateShowtimeAnnotations();
}

function resetUtc() {
    utcOverrideValue = 1;
    updateShowtimeAnnotations();
}

function handleMinute() {
    updateAllDressingRoomButtons();
    window.setTimeout(handleMinute, 60000);
}

function handleSecond() {
    updateShowtimeAnnotations();
    window.setTimeout(handleSecond, 1000);
}

function handleMirrorAnimation() {
    document.querySelectorAll(".mirror-animated")
        .forEach(value => {
            value.classList.toggle("mirrored");
        });
    document.querySelectorAll(".speaker")
        .forEach(value => {
            if (value.textContent == "🔊") {
                value.textContent = "🔈";
            } else {
                value.textContent = "🔊";
            }
        });
    window.setTimeout(handleMirrorAnimation, 500);
}

function onLoad() {
    showCurrentDay();
    handleMinute();
    handleSecond;
    handleMirrorAnimation();
}
