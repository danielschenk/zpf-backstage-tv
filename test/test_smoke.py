"""Smoke tests"""


def test_programme(session):
    programme = session.get("programme").json()
    acts = programme["acts"]
    assert acts["foo"]["name"] == "Foo"
    assert acts["bar"]["name"] == "Bar"


def test_itinerary(session):
    itinerary = session.get("itinerary").json()
    assert itinerary["foo"]["dressing_room"] == "Room 1"
    assert itinerary["bar"]["dressing_room"] == "None"

    session.put("itinerary/foo/dressing_room", data="Room 42".encode("utf-8"))

    itinerary = session.get("itinerary").json()
    assert itinerary["foo"]["dressing_room"] == "Room 42"
