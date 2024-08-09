import os
import pathlib
import logging
import requests
from cachecontrol import CacheControl
from cachecontrol.caches.file_cache import FileCache
import calendar
from cachecontrol.heuristics import BaseHeuristic
from datetime import datetime, timedelta
import re
from email.utils import parsedate, formatdate
import bs4
import sentry_sdk

from . import errors


class Website:
    ZPF_URL = "https://www.zomerparkfeest.nl"
    PROGRAMME_BASE_URL = ZPF_URL + "/programma"
    PROGRAMME_SCHEMA_VERSION = "1.0"
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

    def get_acts(self, stage):
        url = f"{self.PROGRAMME_BASE_URL}/locaties/{stage.lower()}"
        self._logger.info(f"fetching {url}...")
        resp = self.session.get(url)
        resp.raise_for_status()
        soup = bs4.BeautifulSoup(resp.text, features=self._BS4_FEATURES)
        links = soup.find_all("a", href=re.compile("/programma/[^/]+/?$"))
        if not any(links):
            raise errors.ZpfWebsiteError("no acts found on page")

        acts = []
        for link in links:
            if link["href"].endswith("locaties/"):
                continue
            try:
                name = link.find("h2").find("span").text.strip()
            except Exception as e:
                self._logger.error(e)
                sentry_sdk.capture_exception(e)
                continue

            act = {}
            act["name"] = name
            act["url"] = link["href"]
            acts.append(act)

        return acts

    def get_description(self, act_url):
        self._logger.info(f"fetching {act_url}...")
        resp = self.session.get(act_url)
        resp.raise_for_status()
        resp.encoding = "utf-8"
        soup = bs4.BeautifulSoup(resp.text, features=self._BS4_FEATURES)
        try:
            paragraph = soup.find("section", class_="prose").find("p")
            return re.sub("<[^<]+?>", "", paragraph.text)
        except Exception as e:
            self._logger.error(f"unable to find description: {e}")
            raise errors.ZpfWebsiteError("unable to find description") from e


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
