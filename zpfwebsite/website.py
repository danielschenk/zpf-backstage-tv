import os
import pathlib
import hashlib
from typing import Optional, List, Mapping
import logging
import requests
from cachecontrol import CacheControl
from cachecontrol.caches.file_cache import FileCache
import calendar
from cachecontrol.heuristics import BaseHeuristic
from datetime import datetime, timedelta
from email.utils import parsedate, formatdate
import bs4

from . import errors


class Website:
    ZPF_URL = "https://www.zomerparkfeest.nl"
    BLOCK_DIAGRAM_BASE_URL = ZPF_URL + "/programma/schema/"
    PROGRAMME_SCHEMA_VERSION = "0.2"
    _BS4_FEATURES = "html.parser"

    def __init__(self, force_cache=False) -> None:
        home = pathlib.Path(os.path.expanduser("~"))
        cache_dir = "requests-cache-dev" if force_cache else "requests_cache"
        cache_path = home / ".python-zpfwebsite" / cache_dir
        self._logger = logging.getLogger(__class__.__name__)
        self._logger.debug(f"storing requests cache in: {cache_path}")
        cache_path.mkdir(parents=True, exist_ok=True)

        heuristic = _DaysHeuristic(7) if force_cache else None
        self.session = CacheControl(requests.Session(),
                                    cache=FileCache(cache_path),
                                    heuristic=heuristic)

        # Aggressively cache act detail pages. We only use them for the
        # description, which is unlikely to change, and the ZPF WiFi can
        # be terribly slow
        self.details_session = CacheControl(requests.Session(),
                                            cache=FileCache(cache_path),
                                            heuristic=_DaysHeuristic(1))

    def get_programme(self, stage_list: Optional[List[str]] = None) -> Mapping[str, Mapping]:
        """Gets festival programme"""

        days = self.get_programme_days()
        weekdays = [day["weekday_name"] for day in days]
        days_of_month = [day["day_of_month"] for day in days]
        programme = {
            "fetch_time": datetime.now().isoformat(),
            "acts": {},
            "schema_version": self.PROGRAMME_SCHEMA_VERSION,
        }
        for day, day_of_month, url in zip(weekdays, days_of_month,
                                          self.get_programme_day_urls()):
            self._logger.info(f'getting {day}...')
            response = self.session.get(url)
            response.raise_for_status()
            self._parse_block_diagram(response.content, day, day_of_month, programme["acts"],
                                      stage_list)
        self._logger.info("done getting programme")

        return programme

    def get_programme_days(self):
        days = []
        for url in self.get_programme_day_urls():
            if url.endswith("/"):
                url = url[:-1]
            last_component = url.rsplit("/", maxsplit=1)[1]
            parts = last_component.split("-")
            days.append({
                "weekday_name": parts[0],
                "day_of_month": int(parts[1]),
                "month_name": parts[2],
            })
        return days

    def get_programme_day_urls(self):
        response = self.session.get(self.BLOCK_DIAGRAM_BASE_URL)
        response.raise_for_status()
        soup = bs4.BeautifulSoup(response.content, features=self._BS4_FEATURES)
        urls = []
        for link in soup.find_all("a", string=("DO", "VR", "ZA", "ZO")):
            urls.append(link["href"])
        if not urls:
            raise errors.ZpfWebsiteError("Day URLs could not be found")
        return urls

    def _parse_block_diagram(self, html, day, day_of_month, program: dict, stage_list=None):
        """Parses block diagram for single day and adds results to the given program
        dict"""

        soup = bs4.BeautifulSoup(html, features=self._BS4_FEATURES)
        stage_rows = soup.find_all("div", class_="border-dashed")
        if not stage_rows:
            raise errors.ZpfWebsiteError("no stage rows found")

        for row in stage_rows:
            preceding_div = row.previousSibling
            assert preceding_div.name == "div"
            assert "translate-y-stage-name" in preceding_div["class"]
            stage_name = preceding_div.text
            if stage_list is not None and stage_name not in stage_list:
                continue

            acts = row.find_all("div", class_="flex-auto")
            if not acts:
                raise errors.ZpfWebsiteError("no acts found")

            for act in acts:
                link = act.find("a")
                name = link.text

                hash = hashlib.sha1(name.encode("utf8")).hexdigest()
                if hash not in program:
                    entry = program[hash] = {}
                    entry["name"] = name
                    entry["url"] = link["href"]

                    self._logger.debug(f'getting and parsing page for act "{entry["name"]}"')
                    response = self.details_session.get(entry["url"])
                    response.raise_for_status()
                    soup_act = bs4.BeautifulSoup(response.content, features=self._BS4_FEATURES)
                    paragraphs = soup_act.find_all("p")
                    entry["description"] = "\n\n".join(p.text for p in paragraphs)
                    entry["description_html"] = "".join(str(p) for p in paragraphs)
                    entry["shows"] = []
                else:
                    entry = program[hash]

                info_text = act.find("span", class_="text-sm").text
                time_text = info_text.splitlines()[1].strip().replace('"', '')
                start, end = [t.strip() for t in time_text.split("-", maxsplit=1)]
                entry["shows"].append({
                    "day": day,
                    "day_of_month": day_of_month,
                    "start": start,
                    "end": end,
                    "stage": stage_name,
                })


# Modified example from cachecontrol documentation
class _DaysHeuristic(BaseHeuristic):
    def __init__(self, days) -> None:
        super().__init__()
        self._days = days

    def update_headers(self, response):
        if 'date' in response.headers:
            date = parsedate(response.headers['date'])
        else:
            date = datetime.now().timetuple()
        expires = datetime(*date[:6]) + timedelta(days=self._days)
        return {
            'expires' : formatdate(calendar.timegm(expires.timetuple())),
            'cache-control' : 'public',
        }

    def warning(self, response):
        msg = 'Automatically cached! Response is Stale.'
        return '110 - "%s"' % msg
