function addEntry() {
    var newEntry = document.getElementById("template-entry").cloneNode(true);
    newEntry.removeAttribute("id");
    newEntry.style.display = "block";
    document.getElementById("reminder-entries").appendChild(newEntry);
}

function removeEntry(button) {
    button.parentElement.remove();
}
