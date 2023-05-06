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


def test_programme_virgin(session_virgin):
    programme = session_virgin.get("programme").json()
    acts = programme["acts"]
    assert acts["ca532add9e11272b77940d5e30ddcf17a6be3845"]["name"] == "Bente"


def test_itinerary_virgin(session_virgin):
    itinerary = session_virgin.get("itinerary").json()
    assert itinerary["ca532add9e11272b77940d5e30ddcf17a6be3845"]["dressing_room"] == "None"
