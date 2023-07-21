"""Tests for the zpfwebsite module"""
import zpfwebsite


def test_get_programme_days():
    website = zpfwebsite.Website()
    days = website.get_programme_days()
    assert len(days) == 4

    weekdays = [day["weekday_name"] for day in days]
    assert weekdays == ["donderdag", "vrijdag", "zaterdag", "zondag"]

    assert all(isinstance(day["day_of_month"], int) for day in days)
    assert all(day["month_name"] in ("augustus", "september") for day in days)
