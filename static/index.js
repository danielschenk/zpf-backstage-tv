function setDressingRoom(actKey, roomNumber) {
    hideButtons(actKey);
    fetch("itinerary/" + actKey + "/dressing_room", {
        "method": "PUT",
        "body": roomNumber
    }).then(response => {
        if (response.ok) {
            updateItineraryView(actKey);
            showToast("saved");
        } else {
            handleSetItineraryItemError();
        }
    }, handleSetItineraryItemError);
}

function setCustomDressingRoom(actKey) {
    setDressingRoom(actKey,
        document.getElementById(actKey + "-custom-room").value);
}

function setItineraryItem(actKey, itemKey) {
    hideButtons(actKey);
    fetch("itinerary/" + actKey + "/" + itemKey, {
        "method": "PUT",
        "body": document.getElementById(`${actKey}-${itemKey}`).value
    }).then(response => {
        if (response.ok) {
            updateItineraryView(actKey);
            showToast("saved");
        } else {
            handleSetItineraryItemError();
        }
    }, handleSetItineraryItemError);
}

function handleSetItineraryItemError() {
    showToast("general-error");
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
            showToast("itinerary-error");
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
            hideToast("itinerary-error");
        }, () => {
            showButtons(actKey);
            showToast("itinerary-error");
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

    document.querySelectorAll(`input.free-field[data-act="${key}"]`)
        .forEach(input => {
            let key = input.dataset.field;
            if (key in data) {
                input.value = data[key];
            } else {
                input.value = '';
            }
        });
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

function showPane(pane) {
    let div = document.getElementById("pane-" + pane);
    if (div == null) {
        console.warn(`no pane named ${pane}`);
        return;
    }

    document.querySelectorAll("div.pane, ul.navigation li a, .nav-indicator")
        .forEach(value => {
            value.classList.remove("selected");
        });
    document.querySelector(`ul.navigation li a[href="#${pane}"]`).classList.add("selected");
    document.getElementById("nav-indicator-#" + pane).classList.add("selected");
    div.classList.add("selected");
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
        showPane(dayToText[day]);
    } else {
        showPane("donderdag");
    }
}

let utcOverrideValue = -1;

function updateShowtimeAnnotations() {
    let utc;
    if (utcOverrideValue > -1) {
        utc = utcOverrideValue;
    } else {
        utc = Math.round(new Date().getTime() / 1000);
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

var toastTimeouts = {};

function showToast(name, timeout=3000) {
    if (name in toastTimeouts) {
        // already on screen
        clearTimeout(toastTimeouts[name]);
        hideToast(name);
        // re-show after a small delay (to make clear it's the same toast, but again)
        setTimeout(() => {showToast(name, timeout);}, 250);
        return;
    }

    document.getElementById("toast-" + name).classList.add("active");
    if (timeout > 0) {
        toastTimeouts[name] = setTimeout(() => { hideToast(name); }, timeout);
    }
}

function hideToast(name) {
    document.getElementById("toast-" + name).classList.remove("active");
    if (name in toastTimeouts) {
        delete toastTimeouts[name];
    }
}

function onLoad() {
    addEventListener("hashchange", event => {
        let pos = event.newURL.search("#");
        if (pos > 0) {
            showPane(event.newURL.substring(pos + 1));
        }
    });

    showCurrentDay();
    handleMinute();
    handleSecond();
    handleMirrorAnimation();
}
