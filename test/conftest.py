"""Common fixtures"""

import pytest
import requests
import urllib.parse
import bs4


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
def session(host):
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
    print(response)
    print(response.history)
    assert response.history[0].headers["Location"] == "/"

    return session
