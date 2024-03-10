function onLoad() {
    var entry;
    entry = addEntry();
    entry.querySelector("select.minute-value").value = "6";
    entry.querySelector("select.before-after").value = "-";
    entry.querySelector("select.reference").value = "start_utc";
    entry = addEntry();
    entry.querySelector("select.minute-value").value = "6";
    entry.querySelector("select.before-after").value = "-";
    entry.querySelector("select.reference").value = "end_utc";
    updateUrl();
}

function addEntry() {
    var newEntry = document.getElementById("template-entry").cloneNode(true);
    newEntry.removeAttribute("id");
    newEntry.classList.remove("skip");
    newEntry.style.display = "block";
    document.getElementById("add-button-entry").insertAdjacentElement("beforebegin",
        newEntry);
    updateUrl();
    return newEntry;
}

function removeEntry(button) {
    button.parentElement.remove();
    updateUrl();
}

function updateUrl() {
    var first = true;
    var relativeUrl = "/programme.ics";
    document.getElementById("reminder-entries")
        .querySelectorAll("li").forEach(item => {
            if (item.classList.contains("skip"))
            {
                return;
            }

            relativeUrl += first ? "?reminders=" : ";";
            relativeUrl += item.querySelector("select.reference").value;
            relativeUrl += ".";
            relativeUrl += item.querySelector("select.before-after").value;
            relativeUrl += item.querySelector("select.minute-value").value;
            first = false;
        });

    if (first) {
        // no entries were processed, prevent default reminders you get for no url params
        relativeUrl += "?enable_reminders=0";
    }

    var webcalUrl = "webcal://" + window.location.host + relativeUrl;
    document.getElementById("url").innerText = webcalUrl;
    document.getElementById("apple-url").href = webcalUrl;
    var googleUrl = "https://calendar.google.com/calendar/r?cid=" + webcalUrl;
    document.getElementById("google-url").href = googleUrl;
}

function copy() {
    navigator.clipboard.writeText(document.getElementById("url").innerText);
}
