"""Smoke tests"""


def test_programme(session):
    session.get("programme")
