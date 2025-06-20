import pytest
import responses
from ..api import Api


BASE_URL = "https://www.foo.fake"


@pytest.fixture
def programs():
    return [
        {"title": "awesome band", "location": {"id": 1}},
        {"title": "boring band", "location": {"id": 2}},
    ]


@pytest.fixture
def locations():
    return [
        {"title": "Amigo", "id": 1},
        {"title": "Zelt", "id": 2},
    ]


@pytest.fixture
def mock_responses(programs, locations):
    with responses.RequestsMock() as rsps:
        rsps.get(f"{BASE_URL}/programs", json=programs)
        rsps.get(f"{BASE_URL}/locations", json=locations)
        yield


@pytest.fixture
def api(mock_responses):
    return Api(BASE_URL)


def test_get_programs(api, programs):
    assert api.get_programs() == programs


def test_get_programs_by_location(api, programs):
    assert api.get_programs("Amigo") == [programs[0]]
    assert api.get_programs("Zelt") == [programs[1]]


def test_get_programs_by_location_case_insensitive(api, programs):
    assert api.get_programs("amigo") == [programs[0]]


def test_invalid_location(api):
    with pytest.raises(ValueError):
        api.get_programs("Nonexistent")
