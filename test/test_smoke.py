"""Smoke tests"""


def test_programme(session):
    programme = session.get("programme").json()
    acts = programme["acts"]
    assert acts["foo"]["name"] == "Foo"
    assert acts["foo"]["description"] == "Description of Foo"
    assert acts["bar"]["name"] == "Bar"
    assert acts["bar"]["description"] == "Description of Bar"


def test_itinerary(session):
    itinerary = session.get("itinerary").json()
    assert itinerary["foo"]["dressing_room"] == "Room 1"
    assert itinerary["bar"]["dressing_room"] == "None"

    session.put("itinerary/foo/dressing_room", data="Room 42".encode("utf-8"))

    itinerary = session.get("itinerary").json()
    assert itinerary["foo"]["dressing_room"] == "Room 42"


def test_programme_virgin(session_virgin):
    programme = session_virgin.get("programme").json()
    assert "acts" in programme


def test_itinerary_virgin(session_virgin):
    session_virgin.get("itinerary").json()
