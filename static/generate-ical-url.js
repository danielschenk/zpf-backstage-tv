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
    newEntry.style.display = "block";
    document.getElementById("reminder-entries").appendChild(newEntry);
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
            if (item.id == "template-entry")
            {
                return;
            }

            relativeUrl += first ? "?reminder=" : "&reminder=";
            relativeUrl += item.querySelector("select.before-after").value;
            relativeUrl += item.querySelector("select.minute-value").value;
            relativeUrl += ".";
            relativeUrl += item.querySelector("select.reference").value;
            first = false;
        });

    document.getElementById("url").innerText = window.location.protocol + "//" + window.location.host +
        relativeUrl;
}
