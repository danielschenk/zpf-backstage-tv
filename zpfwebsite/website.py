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
import re
from email.utils import parsedate, formatdate
import bs4

# from . import errors


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

        # Aggressively cache act detail pages. We only use them for the
        # description, which is unlikely to change, and the ZPF WiFi can
        # be terribly slow
        self.details_session = CacheControl(requests.Session(),
                                            cache=FileCache(cache_path),
                                            heuristic=_DaysHeuristic(1))

    def get_act_urls(self):
        resp = self.session.get(self.PROGRAMME_BASE_URL)
        resp.raise_for_status()
        soup = bs4.BeautifulSoup(resp.content, features=self._BS4_FEATURES)
        for link in soup.find_all("a", href=re.compile("programma/.+")):
            print(link)

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
