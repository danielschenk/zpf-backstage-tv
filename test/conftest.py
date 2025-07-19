"""Common fixtures"""

import subprocess
from contextlib import contextmanager
from pathlib import Path
import shutil
import time

import pytest
import requests
import urllib.parse
import bs4


TEST_DIR = Path(__file__).parent
INSTANCE_DIR = TEST_DIR / "instance"
ROOT_DIR = TEST_DIR.parent


class SessionWithBaseUrl(requests.Session):
    def __init__(self, base_url):
        super().__init__()
        self.base_url = base_url

    def request(self, method, url, *args, **kwargs):
        joined_url = urllib.parse.urljoin(self.base_url, url)
        return super().request(method, joined_url, *args, **kwargs)


@pytest.fixture
def host():
    return "http://localhost:5000"


@pytest.fixture
def session(host, app):
    return create_session(host)


@pytest.fixture
def session_virgin(host, app_virgin):
    return create_session(host)


def create_session(host):
    session = SessionWithBaseUrl(host)

    response = session.get("/login")
    soup = bs4.BeautifulSoup(response.text, "html.parser")
    csrf_input = soup.find("input", {"id": "csrf_token"})

    data = {
        "csrf_token": csrf_input.attrs["value"],
        "username": "test",
        "password": "test",
        "submit": "Submit",
    }
    headers = {"Upgrade-Insecure-Requests": "1"}
    response = session.post("/login", data=data, headers=headers)
    assert response.history[0].headers["Location"] == "/"

    return session


@contextmanager
def app_process(tmp_path: Path, virgin=False):
    if not virgin:
        # copy instance data to a tempdir, so that we always start app with same state
        shutil.copytree(INSTANCE_DIR, tmp_path, dirs_exist_ok=True)

    config = (TEST_DIR / "settings.py").absolute()
    with subprocess.Popen(
        [
            "flask",
            "--app",
            f'app:create_app(instance_path="{str(tmp_path)}",config_filename="{str(config)}")',
            "run",
        ],
        cwd=ROOT_DIR,
    ) as p:
        time.sleep(2)
        assert p.poll() is None
        yield
        p.kill()


@pytest.fixture
def app(tmp_path):
    with app_process(tmp_path):
        yield


@pytest.fixture
def app_virgin(tmp_path):
    with app_process(tmp_path, virgin=True):
        yield
