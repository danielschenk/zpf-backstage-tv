"""Common fixtures"""

import multiprocessing
import pathlib

import pytest
import requests
import urllib.parse
import bs4
import app as flask_app


TEST_DIR = pathlib.Path(__file__).parent
INSTANCE_DIR = TEST_DIR / "instance"

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
    session = SessionWithBaseUrl(host)

    response = session.get("/login")
    soup = bs4.BeautifulSoup(response.text, "html.parser")
    csrf_input = soup.find("input", {"id": "csrf_token"})

    data = {
        "csrf_token": csrf_input.attrs["value"],
        "username": "test",
        "password": "test",
        "submit": "Submit"
    }
    headers = {
        "Upgrade-Insecure-Requests": "1"
    }
    response = session.post("/login", data=data, headers=headers)
    assert response.history[0].headers["Location"] == "/"

    return session


@pytest.fixture
def app():
    the_app = flask_app.create_app(instance_path=INSTANCE_DIR,
                                   config_filename=INSTANCE_DIR / "settings.py")
    process = multiprocessing.Process(target=the_app.run)
    process.start()
    yield
    process.terminate()
    process.join()
