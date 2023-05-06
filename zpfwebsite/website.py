import os
import pathlib
import hashlib
from typing import Optional, List, Mapping
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
    ZPF_URL = "http://www.zomerparkfeest.nl"
    BLOCK_DIAGRAM_BASE_URL = ZPF_URL + "/programma/schema/"
    _BS4_FEATURES = "html.parser"

    def __init__(self, force_cache=False) -> None:
        home = pathlib.Path(os.path.expanduser("~"))
        cache_dir = "requests-cache-dev" if force_cache else "requests_cache"
        cache_path = home / ".python-zpfwebsite" / cache_dir
        print(f"storing requests cache in: {cache_path}")
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

        day_urls = [
            ('donderdag', 'donderdag-25-augustus'),
            ('vrijdag', 'vrijdag-26-augustus'),
            ('zaterdag', 'zaterdag-27-augustus'),
            ('zondag', 'zondag-28-augustus'),
        ]
        programme = {"fetch_time": datetime.now().isoformat(), "acts": {}}
        for day, url in day_urls:
            print(f'getting {day}...')
            html = self.session.get(self.BLOCK_DIAGRAM_BASE_URL + url).content
            self._parse_block_diagram(html, day, programme["acts"], stage_list)
        print("done getting programme")

        return programme

    def _parse_block_diagram(self, html, day, program: dict, stage_list=None):
        """Parses block diagram for single day and adds results to the given program
        dict"""

        soup = bs4.BeautifulSoup(html, features=self._BS4_FEATURES)
        stage_rows = soup.find_all("div", class_="border-dashed")
        if not stage_rows:
            raise errors.ZpfWebsiteError("no stage rows found")

        for row in stage_rows:
            stage_name = row.find("div", class_="translate-y-stage-name").text
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

                    print(f'getting and parsing page for act "{entry["name"]}"')
                    act_html = self.details_session.get(entry["url"]).content
                    soup_act = bs4.BeautifulSoup(act_html, features=self._BS4_FEATURES)
                    paragraphs = soup_act.find_all("p")
                    entry["description"] = "\n\n".join(p.text for p in paragraphs)
                    entry["description_html"] = "".join(str(p) for p in paragraphs)
                    entry["shows"] = []
                else:
                    entry = program[hash]

                info_text = act.find("span", class_="text-sm").text
                time_text = info_text.splitlines()[1].strip().replace('"', '')
                start, end = [t.strip() for t in time_text.split("-", maxsplit=1)]
                entry["shows"].append({"day": day, "start": start, "end": end, "stage": stage_name})


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
