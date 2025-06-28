"""Common fixtures"""

import multiprocessing
import pathlib
import tempfile
import shutil
import time

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


@pytest.fixture
def app():
    # copy instance data to a tempdir, so that we always start app with same state
    with tempfile.TemporaryDirectory() as temp_instance:
        shutil.copytree(INSTANCE_DIR, temp_instance, dirs_exist_ok=True)
        the_app = flask_app.create_app(
            instance_path=temp_instance, config_filename=TEST_DIR / "settings.py"
        )
        process = multiprocessing.Process(target=the_app.run)
        process.start()
        time.sleep(2)
        yield
        process.terminate()
        process.join()


@pytest.fixture
def app_virgin():
    with tempfile.TemporaryDirectory() as temp_instance:
        the_app = flask_app.create_app(
            instance_path=temp_instance, config_filename=TEST_DIR / "settings.py"
        )
        process = multiprocessing.Process(target=the_app.run)
        process.start()
        time.sleep(2)
        yield
        process.terminate()
        process.join()
