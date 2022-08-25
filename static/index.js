function setDressingRoom(actKey, roomNumber) {
    hideButtons(actKey);
    fetch("itinerary/" + actKey + "/dressing_room", {
        "method": "PUT",
        "body": roomNumber
    }).then(response => {
        if (response.ok) {
            updateItineraryView(actKey);
        } else {
            handleSetItineraryItemError();
        }
    }, handleSetItineraryItemError);
}

function setCustomDressingRoom(actKey) {
    setDressingRoom(actKey,
        document.getElementById(actKey + "-custom-room").value);
}

function setItineraryItem(actKey, itemKey, inputId) {
    hideButtons(actKey);
    fetch("itinerary/" + actKey + "/" + itemKey, {
        "method": "PUT",
        "body": document.getElementById(inputId).value
    }).then(response => {
        if (response.ok) {
            updateItineraryView(actKey);
        } else {
            handleSetItineraryItemError();
        }
    }, handleSetItineraryItemError);
}

function handleSetItineraryItemError() {
    window.alert("Failed to save");
    showButtons();
}

function updateItineraryView(actKey) {
    hideButtons(actKey);

    let url = "itinerary";
    if (actKey != undefined) {
        url += "/" + actKey;
    }
    fetch(url)
        .then(response => response.json(), () => {
            window.alert("Failed to fetch itinerary");
            return Promise.reject(Error("Failed to fetch itinerary"));
        })
        .then(data => {
            let selector = "button.dressing-room";
            if (actKey != undefined) {
                selector += ".act-" + actKey;
            }
            document.querySelectorAll(selector)
                .forEach(value => {
                    value.classList.remove("selected");
                });
            if (actKey != undefined) {
                updateItineraryViewElements(actKey, data);
            } else {
                for (key in data) {
                    updateItineraryViewElements(key, data[key]);
                }
            }

            showButtons(actKey);
        }, () => {
            showButtons(actKey);
        });
}

function updateItineraryViewElements(key, data) {
    let room = data["dressing_room"];
    let button = document.getElementById(key + "-" + room);
    if (button == null) {
        input = document.getElementById(key + "-custom-room");
        if (input != null) {
            input.value = room;
            button = document.getElementById(key + "-custom-room-button");
        } else {
            console.warn("room buttons for act " + key + " were not found");
        }
    }
    if (button != null) {
        button.classList.add("selected");
    }

    for (itineraryKey in data) {
        if (itineraryKey == "dressing_room") {
            continue;
        }
        let input = document.getElementById(key + "-" + itineraryKey);
        if (input == null) {
            console.warn(itineraryKey + " input for act " + key + " not found");
        }
        input.value = data[itineraryKey];
    }
}

function hideButtons(actKey) {
    let selector = "div.dressing-room-loader";
    if (actKey != undefined) {
        selector += ".act-" + actKey;
    }
    document.querySelectorAll(selector)
        .forEach(value => {
            value.style.display = "block";
        });
}

function showButtons(actKey) {
    let selector = "div.dressing-room-loader";
    if (actKey != undefined) {
        selector += ".act-" + actKey;
    }

    window.top.document.querySelectorAll(selector)
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
        0: "zondag"
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
    utcOverrideValue = -1;
    updateShowtimeAnnotations();
}

function handleMinute() {
    updateItineraryView();
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
    handleSecond();
    handleMirrorAnimation();
}
