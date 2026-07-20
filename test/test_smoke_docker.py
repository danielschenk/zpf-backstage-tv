"""Docker smoke tests - tests the app running in a Docker container"""

from icalendar import Calendar


def test_docker_programme(session_docker):
    programme = session_docker.get("programme").json()
    acts = programme["acts"]
    assert acts["foo"]["name"] == "Foo"
    assert acts["foo"]["description"] == "Description of Foo"
    assert acts["bar"]["name"] == "Bar"
    assert acts["bar"]["description"] == "Description of Bar"
    assert "baz" not in acts  # different stage


def test_docker_itinerary(session_docker):
    itinerary = session_docker.get("itinerary").json()
    assert itinerary["foo"]["dressing_room"] == "Room 1"
    assert itinerary["bar"]["dressing_room"] == "None"

    session_docker.put("itinerary/foo/dressing_room", data="Room 42".encode("utf-8"))

    itinerary = session_docker.get("itinerary").json()
    assert itinerary["foo"]["dressing_room"] == "Room 42"


def test_docker_programme_virgin(session_docker_virgin):
    programme = session_docker_virgin.get("programme").json()
    assert "acts" in programme


def test_docker_itinerary_virgin(session_docker_virgin):
    session_docker_virgin.get("itinerary").json()


def test_docker_icalendar(session_docker):
    calendar = Calendar.from_ical(session_docker.get("programme.ics").text)
    act_names = [event.get("SUMMARY") for event in calendar.events]
    assert "Foo" in act_names
    assert "Bar" in act_names


def test_docker_icalendar_virgin(session_docker_virgin):
    calendar = Calendar.from_ical(session_docker_virgin.get("programme.ics").text)
    assert len(calendar.events) == 0
