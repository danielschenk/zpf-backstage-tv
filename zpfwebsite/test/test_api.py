import pytest
import responses
from ..api import Api, find_best_matching_program


BASE_URL = "https://www.foo.fake"


@pytest.fixture
def programs():
    return [
        {
            "title": "awesome band",
            "location": {"id": 1},
            "timeline": [
                {"location": {"id": 1}, "title": "show at amigo"},
                {"location": {"id": 2}, "title": "show at zelt"},
                {"location": None, "title": "unknown location"},
            ],
        },
        {
            "title": "boring band",
            "location": {"id": 2},
            "timeline": [
                {"location": {"id": 2}, "title": "show at zelt"},
                {"location": {"id": 1}, "title": "show at amigo"},
            ],
        },
        {"title": "nowhere band", "location": None},
        {"title": "band in limbo", "location": {}},
    ]


@pytest.fixture
def locations():
    return [
        {"title": "Amigo", "id": 1},
        {"title": "Zelt", "id": 2},
    ]


@pytest.fixture
def mock_responses(programs, locations):
    with responses.RequestsMock(assert_all_requests_are_fired=False) as rsps:
        rsps.get(f"{BASE_URL}/programs", json=programs)
        rsps.get(f"{BASE_URL}/locations", json=locations)
        yield


@pytest.fixture
def api(mock_responses):
    return Api(BASE_URL)


def test_get_programs(api, programs):
    assert api.get_programs() == programs


def test_get_programs_by_location(api, programs):
    amigo_programs = api.get_programs("Amigo")
    assert len(amigo_programs) == 1
    assert amigo_programs[0]["title"] == programs[0]["title"]
    assert amigo_programs[0]["timeline"] == [programs[0]["timeline"][0]]

    zelt_programs = api.get_programs("Zelt")
    assert len(zelt_programs) == 1
    assert zelt_programs[0]["title"] == programs[1]["title"]
    assert zelt_programs[0]["timeline"] == [programs[1]["timeline"][0]]


def test_get_programs_by_location_case_insensitive(api, programs):
    amigo_programs = api.get_programs("amigo")
    assert len(amigo_programs) == 1
    assert amigo_programs[0]["title"] == programs[0]["title"]
    assert amigo_programs[0]["timeline"] == [programs[0]["timeline"][0]]


def test_invalid_location(api):
    with pytest.raises(ValueError):
        api.get_programs("Nonexistent")


def test_find_best_matching_program():
    programs = [
        {"title": "awesome band", "description": "a"},
        {"title": "boring band", "description": "b"},
    ]
    assert find_best_matching_program(programs, "awesome band") is programs[0]
    assert find_best_matching_program(programs, "awsome band") is programs[0]


def test_find_best_matching_program_no_match():
    programs = [
        {"title": "awesome band", "description": "a"},
        {"title": "boring band", "description": "b"},
    ]
    with pytest.raises(ValueError):
        find_best_matching_program(programs, "completely different")


def test_find_best_matching_program_diacritics():
    programs = [{"title": "Zoë", "description": "a"}]
    with pytest.raises(ValueError):
        find_best_matching_program(programs, "Zoe")
    assert find_best_matching_program(programs, "Zoe", remove_diacritics=True) is programs[0]
