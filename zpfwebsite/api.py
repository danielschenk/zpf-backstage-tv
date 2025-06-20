import requests
import logging
from typing import Any


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
            programs = [
                p for p in programs if "location" in p and p["location"]["id"] == location_id
            ]
        return programs

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
