#!/usr/bin/env python3

"""Flask app which serves as the backend for the Zomerparkfeest Amigo backstage TV"""

from collections import defaultdict
import threading
import datetime
import subprocess
import pathlib
from typing import OrderedDict, Any
import os
from dataclasses import dataclass
import uuid
from urllib.parse import urlparse, urljoin
import logging
from difflib import SequenceMatcher
import flask
from flask import Flask, render_template, jsonify, make_response, request, Response
from flask_login import LoginManager, login_user, login_required
from flask_bootstrap import Bootstrap
from src import users, storage
from apscheduler.schedulers.background import BackgroundScheduler
import icalendar
import requests.auth
import sentry_sdk
import bs4

import zpfwebsite
from src.productionplanner import remove_friends_night_tag

APP_DIR = pathlib.Path(__file__).parent
DEFAULT_INSTANCE_PATH = APP_DIR / "instance"

scheduler = BackgroundScheduler()

# from datetime int to dutch
LEGACY_DAYS = {
    0: "maandag",
    1: "dinsdag",
    2: "woensdag",
    3: "donderdag",
    4: "vrijdag",
    5: "zaterdag",
    6: "zondag",
}


def get_resource(url, session):
    contents = session.get(url).content

    return contents


def get_version():
    try:
        with open(pathlib.Path(__file__).parent / "VERSION") as f:
            return f.read()
    except FileNotFoundError:
        try:
            cmd = "git describe --always --match 'v*' --dirty".split(" ")
            return subprocess.check_output(cmd).strip().decode("utf-8")
        except subprocess.CalledProcessError:
            return "unknown"


def is_safe_url(target):
    """Tests if target is safe to redirect to

    Source: https://stackoverflow.com/a/61446498
    """
    ref_url = urlparse(request.host_url)
    test_url = urlparse(urljoin(request.host_url, target))
    return test_url.scheme in ("http", "https") and ref_url.netloc == test_url.netloc


@dataclass
class ItineraryField:
    key: str
    display_name: str
    type: str = "text"

    def visible_for(self, act: dict[str, Any]) -> bool:
        return True

    @property
    def class_name(self) -> str:
        return self.__class__.__name__


class WebsiteActNameField(ItineraryField):
    """Special field shown for acts which could not be matched to website act

    With this input field, the act name as used on the public website can be entered to make
    description fetching possible.
    """

    def __init__(self, *args, **kwargs):
        super().__init__("website_act_name", "Act name on website", *args, **kwargs)

    def visible_for(self, act: dict[str, Any]) -> bool:
        return not act["description_available"]


@dataclass
class DescriptionItem:
    description: str | None = None
    name_match: bool = False


def create_app(
    instance_path=DEFAULT_INSTANCE_PATH, config_filename=DEFAULT_INSTANCE_PATH / "settings.py"
):
    app = Flask(__name__, instance_path=str(instance_path))

    app.config.from_object("src.default_settings")
    app.config.from_pyfile(config_filename, silent=True)

    logging.basicConfig(format="%(asctime)s - %(name)10s - %(levelname)7s - %(message)s")
    logging.getLogger().setLevel(app.config.get("LOG_LEVEL", "WARN"))
    logger = logging.getLogger("app")

    dsn = app.config["SENTRY_DSN"]
    if dsn is not None:
        env = app.config["SENTRY_ENV"]
        sentry_sdk.init(dsn=dsn, environment=env)

    _key = app.config["SECRET_KEY"]
    if _key is None:
        logger.warning("SECRET_KEY not set, using random key every restart!")
        _key = os.urandom(64)
    app.config["SECRET_KEY"] = _key

    login_manager = LoginManager()
    login_manager.init_app(app)
    Bootstrap(app)

    api = zpfwebsite.Api(app.config["ZPF_API_URL"] if app.config["UPDATE_PROGRAMME"] else "")

    programme_schema_major = 2

    def programme_validator(programme: dict[str, Any]) -> bool:
        try:
            major, minor = programme["schema_version"].split(".")
            if int(major) < programme_schema_major:
                return False
        except KeyError:
            return False
        return True

    programme_storage = storage.CachedStorage[dict[str, Any], str](
        {"schema_version": f"{programme_schema_major}.0", "acts": {}},
        "programme_cache.json",
        app.open_instance_resource,
        validator=programme_validator,
    )
    acts_storage = storage.CachedStorage[list[dict[str, Any]], str](
        [], "acts.json", app.open_instance_resource
    )
    itinerary_storage = storage.CachedStorage[dict[str, dict], str](
        {}, "itinerary.json", app.open_instance_resource
    )

    def initialize_nonexistent_act_itineraries(acts: list[dict]):
        with itinerary_storage.lock() as itinerary:
            for act in acts:
                key = str(act["id"])
                if key not in itinerary:
                    itinerary[key] = {"dressing_room": "None"}
            itinerary_storage.save()

    def update_acts():
        config = app.config
        session = requests.Session()
        session.auth = requests.auth.HTTPBasicAuth(config["ACTS_USERNAME"], config["ACTS_PASSWORD"])
        logger.info("getting acts...")
        response = session.get(config["ACTS_URL"])
        response.raise_for_status()
        acts_temp = response.json()
        if not isinstance(acts_temp, list):
            logger.error(f"acts in unexpected format: {acts_temp}")
            return

        with acts_storage.lock() as acts:
            acts.clear()
            acts.extend(acts_temp)
            acts_storage.save()

        initialize_nonexistent_act_itineraries(acts_temp)

    def _html_description_to_text(html_description: str) -> str:
        # ensure we keep separation between paragraphs
        html_description = html_description.replace("<p>", "\n\n")
        # remove remaining tags
        # use html.parser to not be dependant on lxml, which is harder to install for some targets,
        # as it contains C code
        return bs4.BeautifulSoup(html_description, "html.parser").get_text().strip()

    def update_act_descriptions():
        try:
            website_acts = api.get_programs("Amigo")
        except Exception as e:
            logger.error(f"could not get acts from website: {e}")
            sentry_sdk.capture_exception(e)
            website_acts = None

        with acts_storage.lock() as acts:
            acts_copy = acts.copy()

        descriptions = defaultdict(DescriptionItem)
        for act in acts_copy:
            key = str(act["id"])
            if not any(event["stage"] == "Amigo" for event in act["timeline"]):
                continue
            if website_acts is None:
                continue

            name = remove_friends_night_tag(act["name"])
            for website_act in website_acts:
                website_act["ratio"] = SequenceMatcher(
                    None, name.lower(), website_act["title"].lower()
                ).ratio()
            best = max(website_acts, key=lambda x: x["ratio"])
            if best["ratio"] < 0.8:
                description = get_description_by_corrected_name(key)
                if description is None:
                    logger.error(f"could not match '{name}' to any of website's acts")
                    descriptions[key].name_match = False
                    continue
            else:
                description = best["description"]

            descriptions[key].name_match = True
            descriptions[key].description = description

        with programme_storage.lock() as programme:
            programme_acts = programme.get("acts", {})
            assert isinstance(programme_acts, dict)
            for key, item in descriptions.items():
                if key not in programme_acts:
                    programme_acts[key] = {}
                act = programme_acts[key]
                act["description_html"] = item.description
                act["name_matched_to_website"] = item.name_match
            programme_storage.save()

    def get_description_by_corrected_name(key: str) -> str | None:

        return None

    if app.config["UPDATE_PROGRAMME"]:
        # make sure we always do one at startup, but don't block server
        def do_initial_fetch():
            update_acts()
            update_act_descriptions()
            with acts_storage.lock() as acts:
                initialize_nonexistent_act_itineraries(acts)

        t = threading.Thread(name="initial_fetch", target=do_initial_fetch, daemon=True)
        t.start()

        scheduler.add_job(update_acts, "interval", minutes=10)
        scheduler.add_job(update_act_descriptions, "interval", minutes=60)
        scheduler.start()

    @app.route("/")
    @login_required
    def serve_index():
        """Main page handler"""
        programme = make_legacy_programme("AMIGO")
        acts_by_day = OrderedDict()

        def get_first_show_start_utc(item: tuple[str, dict[str, Any]]):
            shows: list[dict[str, str]] = item[1]["shows"]
            return sorted(shows, key=lambda show: show["start_utc"])[0]["start_utc"]

        acts = OrderedDict(sorted(programme["acts"].items(), key=get_first_show_start_utc))

        for key, act in acts.items():
            for show in act["shows"]:
                day = show["day"]
                if day not in acts_by_day:
                    acts_by_day[day] = {}
                if key not in acts_by_day[day]:
                    acts_by_day[day][key] = act.copy()

        fetch_time = programme.get("fetch_time", None)
        if fetch_time is not None:
            fetch_time = datetime.datetime.fromisoformat(programme["fetch_time"])
        else:
            fetch_time = None

        dev_mode_display = "block" if "devMode" in request.args else "none"

        free_fields = [WebsiteActNameField()]
        return render_template(
            "index.html",
            acts_by_day=acts_by_day,
            dev_mode_display=dev_mode_display,
            version=get_version(),
            fetch=fetch_time,
            free_fields=free_fields,
        )

    @app.route("/programme")
    def serve_programme():
        programme = make_legacy_programme("AMIGO")
        response = make_response(programme)
        return response

    def make_legacy_programme(stage=None) -> dict[str, dict[str, Any]]:
        """Returns the programme (combined descriptions and itinerary) in legacy format

        This is the format which is still used by the data entry frontend and the AmigoText itself.
        """
        fallback = "Sorry, we konden de beschrijving niet ophalen. :-(\n Laat je verrassen!"
        with acts_storage.lock() as acts, programme_storage.lock() as programme:
            legacy_programme: dict[str, dict[str, Any]] = {}
            legacy_programme["acts"] = legacy_acts = {}

            # Use acts as lead (as this comes from the production planner)
            for act in acts:
                key = str(act["id"])
                try:
                    html = programme["acts"][key]["description_html"]
                    if html is None:
                        html = fallback
                except KeyError:
                    html = fallback

                shows = []
                legacy_act = {
                    "name": act["name"],
                    "shows": shows,
                    "description_html": html,
                    "description": _html_description_to_text(html),
                    "description_available": html != fallback,
                }
                timeline: list[dict[str, Any]] = act["timeline"]
                for event in timeline:
                    if event["type"] == "Showtime":
                        event_stage = event["stage"]
                        show = {"stage": event_stage.upper() if event_stage is not None else None}
                        times = act_event_to_legacy_times(event)
                        show["start"] = times[0]
                        show["end"] = times[1]
                        start = act_datestr_to_datetime(event["start"])
                        end = act_datestr_to_datetime(event["end"])
                        show["start_utc"] = int(start.timestamp())
                        show["end_utc"] = int(end.timestamp())
                        show["day"] = LEGACY_DAYS[festival_weekday(start)]

                        shows.append(show)

                if stage is None or any(show["stage"] == stage for show in shows):
                    legacy_acts[key] = legacy_act

        return legacy_programme

    @app.route("/generate-ical-url")
    def serve_ical_ui():
        return render_template("generate-ical-url.html")

    @app.route("/programme.ics")
    def serve_ical():
        cal = icalendar.Calendar()
        cal.add("PRODID", "-//amigotext//NONSGML amigotext.app.event//EN")
        cal.add("VERSION", "2.0")
        hostname = urlparse(request.base_url).hostname
        days = request.args.get("days", "woensdag;donderdag;vrijdag;zaterdag;zondag").split(";")
        programme = make_legacy_programme("AMIGO")
        itinerary = make_legacy_itinerary()
        for key, act in programme["acts"].items():
            for show in act["shows"]:
                if show["day"] not in days:
                    continue
                event = create_ical_event(key, act, show, itinerary, hostname)

                reminders = []
                for value in request.args.get("reminders", "").split(";"):
                    if not value:
                        continue
                    try:
                        reminders.append(ReminderDefinition.from_urlparam(value))
                    except ValueError:
                        return Response(f"Error in reminder definition: '{value}'", status=400)
                if not reminders:
                    reminders.append(ReminderDefinition("start_utc", -6))
                    reminders.append(ReminderDefinition("end_utc", -6))

                if int(request.args.get("enable_reminders", 1)):
                    try:
                        add_ical_reminders(show, event, reminders)
                    except KeyError as e:
                        return Response(f"Timestamp key '{e.args[0]}' doesn't exist", status=400)

                cal.add_component(event)

        headers = {
            "Cache-Control": "no-cache, no-store",
        }
        return Response(cal.to_ical(), headers=headers, mimetype="text/calendar")

    LEGACY_ITINERARY_KEYS = {
        "Get in": "get_in",
        "Soundcheck": "soundcheck",
        "Linecheck": "linecheck",
    }

    @app.route("/itinerary/<act_key>", methods=["GET"])
    def serve_dressing_room(act_key):
        itinerary = make_legacy_itinerary()
        if act_key not in itinerary:
            return Response("Act does not exist", status=404)

        return jsonify(itinerary[act_key])

    @app.route("/itinerary/<act_key>/<item>", methods=["PUT"])
    @login_required
    def update_dressing_room(act_key, item):
        if item != "dressing_room":
            return Response("everything except dressing_room is read-only", status=405)

        with itinerary_storage.lock() as itinerary:
            if act_key not in itinerary:
                return Response("Act does not exist", status=404)
            itinerary[act_key][item] = request.data.decode("utf-8")
            itinerary_storage.save()
        return "success"

    @app.route("/itinerary")
    def serve_dressing_rooms():
        return make_legacy_itinerary()

    def make_legacy_itinerary():
        with itinerary_storage.lock() as itinerary, acts_storage.lock() as acts:
            full_itinerary = itinerary.copy()

            for act in acts:
                key = str(act["id"])
                itin_item = full_itinerary.get(key, {})
                for event in act["timeline"]:
                    eventtype = event["type"]
                    if eventtype in LEGACY_ITINERARY_KEYS:
                        itin_item[LEGACY_ITINERARY_KEYS[eventtype]] = act_datestr_to_legacy_time(
                            event["start"]
                        )

        return full_itinerary

    @login_manager.user_loader
    def load_user(user_id):
        user = users.TheUser(app.config["USERNAME"], app.config["PASSWORD"])
        if user_id == user.get_id():
            return user
        return None

    @login_manager.unauthorized_handler
    def unauthorized():
        return flask.redirect(flask.url_for("login"))

    @app.route("/login", methods=["GET", "POST"])
    def login():
        form = users.LoginForm()
        if form.validate_on_submit():
            user = users.TheUser(app.config["USERNAME"], app.config["PASSWORD"])
            if (
                request.form["username"] == user.username
                and request.form["password"] == user.password
            ):
                login_user(user, remember=True)
            else:
                flask.flash("Login failed")
                return flask.redirect(flask.url_for("login"))

            flask.flash("Logged in successfully.")

            next = flask.request.args.get("next")
            if not is_safe_url(next):
                return flask.abort(400)

            return flask.redirect(next or flask.url_for("serve_index"))
        return flask.render_template("login.html", form=form)

    return app


def create_ical_event(key, act, show, itinerary, hostname):
    start_utc = show["start_utc"]
    end_utc = show["end_utc"]
    event = icalendar.Event()
    start = datetime.datetime.fromtimestamp(start_utc, datetime.UTC)
    end = datetime.datetime.fromtimestamp(end_utc, datetime.UTC)
    event.add("DTSTART", start)
    event.add("DTEND", end)
    event_uid = f"{key}-{start_utc}"
    event.add("UID", f"{event_uid}@{hostname}")
    event.add("SUMMARY", act["name"])
    event.add("DESCRIPTION", f"{act['description']}")
    dressing_room = itinerary[key].get("dressing_room", None)
    if dressing_room is not None and dressing_room != "None":
        location = f"Dressing room {dressing_room} ({show['stage']})"
    else:
        location = show["stage"]
    event.add("LOCATION", location)

    return event


def add_ical_reminders(show, event, reminders: list["ReminderDefinition"]):
    for reminder in reminders:
        alarm = icalendar.Alarm()
        reference = datetime.datetime.fromtimestamp(show[reminder.reference], tz=datetime.UTC)
        trigger = reference + datetime.timedelta(minutes=reminder.offset_minutes)
        alarm.add("TRIGGER", trigger)
        alarm.add("ACTION", "DISPLAY")
        alarm.add("DESCRIPTION", "Reminder")
        alarm_uid = str(uuid.uuid4())
        alarm.add("UID", alarm_uid)
        alarm.add("X-WR-ALARMUID", alarm_uid)
        event.add_component(alarm)


@dataclass
class ReminderDefinition:
    reference: str
    offset_minutes: int

    @classmethod
    def from_urlparam(cls, value: str):
        reference, offset = value.split(".", maxsplit=1)
        return cls(reference, int(offset))


def hour_minute(time: str):
    return int(time[0:2]), int(time[3:5])


def act_event_to_legacy_times(event: dict[str, str]):
    return act_datestr_to_legacy_time(event["start"]), act_datestr_to_legacy_time(event["end"])


def act_datestr_to_legacy_time(datestr: str):
    return datestr[11:16]


def act_datestr_to_datetime(datestr: str):
    return datetime.datetime.strptime(datestr + " +0200", "%Y-%m-%d %H:%M:%S %z")


def festival_weekday(timepoint: datetime.datetime):
    """Returns the `datetime` day of week for a timepoint, assuming 06:00 for start of new day"""
    return (timepoint - datetime.timedelta(hours=6)).weekday()
