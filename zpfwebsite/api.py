import requests
import logging
from difflib import SequenceMatcher
from typing import Any

from unidecode import unidecode


def find_best_matching_program(
    programs: list[dict[str, Any]], title: str, remove_diacritics: bool = False
) -> dict[str, Any]:
    """Find the program whose title best matches `title`.

    Returns the best matching program if its similarity score is 0.8 or higher, otherwise
    raises `ValueError`. When `remove_diacritics` is True, diacritics are removed from both
    the search title and program titles before comparison.
    """

    def ratio(program: dict[str, Any]) -> float:
        a, b = title, program["title"]
        if remove_diacritics:
            a, b = unidecode(a), unidecode(b)
        return SequenceMatcher(None, a.lower(), b.lower()).ratio()

    best = max(programs, key=ratio)
    if ratio(best) < 0.8:
        raise ValueError(f"could not match '{title}' to any program")
    return best


class Api:
    """API client for the Zomerparkfeest festival website API"""

    def __init__(self, base_url: str):
        self._session = requests.Session()
        self.base_url = base_url
        self._locations_cache: list[dict[str, Any]] | None = None
        self._logger = logging.getLogger(__class__.__name__)

    def get_programs(self, location_name: str | None = None) -> list[dict[str, Any]]:
        """Get programs, optionally filtered by stage name."""
        self._logger.info("Fetching programs")
        response = self._session.get(f"{self.base_url}/programs")
        response.raise_for_status()
        programs = response.json()
        if not isinstance(programs, list):
            raise TypeError("Expected a list of programs from the API")

        if location_name is not None:
            location_id = self.get_location_id(location_name)
            filtered_programs = []
            for program in programs:
                if "location" not in program:
                    continue
                if program["location"] is None or "id" not in program["location"]:
                    continue
                if program["location"]["id"] == location_id:
                    filtered_programs.append(self._filter_program_timeline_by_location(program, location_id))
            return filtered_programs
        return programs

    @staticmethod
    def _filter_program_timeline_by_location(
        program: dict[str, Any], location_id: int
    ) -> dict[str, Any]:
        timeline = program.get("timeline")
        if not isinstance(timeline, list):
            return program

        filtered_timeline = []
        for event in timeline:
            if not isinstance(event, dict):
                continue
            event_location = event.get("location")
            if not isinstance(event_location, dict):
                continue
            if event_location.get("id") == location_id:
                filtered_timeline.append(event)

        filtered_program = program.copy()
        filtered_program["timeline"] = filtered_timeline
        return filtered_program

    def get_locations(self, force=False) -> list[dict[str, Any]]:
        """Get locations (stages)

        This method is cached, we can safely assume the stages do not change during one festival
        edition. If you want to force a refresh, set `force=True`.
        """
        if self._locations_cache is None or force:
            self._logger.info("Fetching locations")
            response = self._session.get(f"{self.base_url}/locations")
            response.raise_for_status()
            self._locations_cache = response.json()
            if not isinstance(self._locations_cache, list):
                raise TypeError("Expected a list of locations from the API")
        return self._locations_cache

    def get_location_id(self, location_name: str) -> int:
        for force in [False, True]:
            for location in self.get_locations(force=force):
                if location["title"].lower() == location_name.lower():
                    return location["id"]
            self._logger.error("Location not found, retrying without cache...")
        raise ValueError(f"Location '{location_name}' not found in the API")
