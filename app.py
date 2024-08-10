#!/usr/bin/env python3

"""Flask app which serves as the backend for the Zomerparkfeest Amigo backstage TV"""

import threading
import json
import datetime
import subprocess
import pathlib
from typing import OrderedDict
from functools import cmp_to_key
import os
from dataclasses import dataclass
import uuid
from urllib.parse import urlparse, urljoin
import logging
import threading
from difflib import SequenceMatcher
import flask
from flask import Flask, render_template, jsonify, make_response, request, Response
from flask_login import LoginManager, login_user, login_required
from flask_bootstrap import Bootstrap
from src import users
from apscheduler.schedulers.background import BackgroundScheduler
import icalendar
import requests.auth
import sentry_sdk

import zpfwebsite.errors


APP_DIR = pathlib.Path(__file__).parent
DEFAULT_INSTANCE_PATH = APP_DIR / "instance"

programme = {
    "schema_version": "1.0",
    "acts": {}
}
programme_lock = threading.Lock()

acts: list[dict[str]] = []
acts_lock = threading.Lock()

itinerary: dict[str, str] = {}
itinerary_lock = threading.Lock()

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
    return test_url.scheme in ('http', 'https') and \
        ref_url.netloc == test_url.netloc


class IncompatibleCacheError(RuntimeError):
    pass


@dataclass
class ItineraryField:
    key: str
    display_name: str
    type: str = "text"


def create_app(instance_path=DEFAULT_INSTANCE_PATH,
               config_filename=DEFAULT_INSTANCE_PATH / "settings.py"):
    app = Flask(__name__, instance_path=instance_path)

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
        logger.warn("SECRET_KEY not set, using random key every restart!")
        _key = os.urandom(64)
    app.config["SECRET_KEY"] = _key

    login_manager = LoginManager()
    login_manager.init_app(app)
    Bootstrap(app)

    def persist_itinerary(itinerary):
        persist_data(itinerary, "itinerary")

    def persist_programme(programme):
        persist_data(programme, "programme_cache")

    def persist_data(data, name):
        write_if_needed(f"{name}.json", json.dumps(data, indent=2))

    def write_if_needed(filename, new_contents, binary=False):
        optional_b = "b" if binary else ""
        try:
            with app.open_instance_resource(filename, f"r{optional_b}") as f:
                if new_contents == f.read():
                    logger.debug(f"contents of {filename} unchanged, skipping write")
                    return
        except FileNotFoundError:
            logger.debug(f"creating {filename}")

        logger.debug(f"writing {filename}")
        with app.open_instance_resource(filename, f"w{optional_b}+") as f:
            f.write(new_contents)

    def initialize_nonexistent_act_itineraries(acts):
        global itinerary
        global itinerary_lock
        with itinerary_lock:
            for act in acts:
                key = str(act["id"])
                if key not in itinerary:
                    itinerary[key] = {"dressing_room": "None"}
            persist_itinerary(itinerary)

    def update_acts():
        config = app.config
        session = requests.Session()
        session.auth = requests.auth.HTTPBasicAuth(config["ACTS_USERNAME"], config["ACTS_PASSWORD"])
        logger.info("getting acts...")
        response = session.get(config["ACTS_URL"])
        response.raise_for_status()
        global acts
        global acts_lock
        acts_temp = response.json()
        with acts_lock:
            acts = acts_temp
        write_if_needed("acts.json", response.content, binary=True)

        initialize_nonexistent_act_itineraries(acts_temp)

    def update_act_descriptions():
        website = zpfwebsite.website.Website()
        website_acts = website.get_acts("amigo")

        global acts
        global acts_lock
        with acts_lock:
            acts_copy = acts.copy()

        descriptions = {}
        for act in acts_copy:
            key = str(act["id"])
            if not any(event["stage"] == "Amigo" for event in act["timeline"]):
                continue
            descriptions[key] = "Sorry, we konden de beschrijving niet ophalen. :-(\n Laat je verrassen!"
            name = act["name"].split(" @ Vrienden")[0].strip()
            for website_act in website_acts:
                website_act["ratio"] = SequenceMatcher(None, name.lower(), website_act["name"].lower()).ratio()
            best = max(website_acts, key=lambda x: x["ratio"])
            if best["ratio"] < 0.8:
                logger.error(f"could not match '{name}' to any of website's acts")
                continue

            try:
                descriptions[key] = website.get_description(best["url"])
            except (zpfwebsite.errors.ZpfWebsiteError, requests.HTTPError) as e:
                logger.error(f"could not get description: {e}")
                sentry_sdk.capture_exception(e)

        global programme
        global programme_lock
        with programme_lock:
            programme_acts = programme.get("acts", {})
            for key, description in descriptions.items():
                if key not in programme_acts:
                    programme_acts[key] = {}
                programme_acts[key]["description"] = description
            persist_programme(programme)

    try:
        global programme
        with app.open_instance_resource("programme_cache.json", "r") as f:
            logger.info("found programme cache on disk")
            programme_temp = json.load(f)
            try:
                major, minor = programme["schema_version"].split(".")
                if int(major) < 1:
                    raise IncompatibleCacheError()
            except KeyError:
                raise IncompatibleCacheError()
            programme = programme_temp
    except (FileNotFoundError, IncompatibleCacheError):
        logger.warning("no programme cache on disk or incompatible, need initial fetch")

    try:
        global acts
        with app.open_instance_resource("acts.json", "r") as f:
            logger.info("found persisted acts on disk")
            acts = json.load(f)
    except FileNotFoundError:
        logger.warning("no acts on disk, need initial fetch")

    try:
        global itinerary
        with app.open_instance_resource("itinerary.json", "r") as f:
            logger.info("found persisted itinerary on disk")
            itinerary = json.load(f)
    except FileNotFoundError:
        logger.warning("no itinerary on disk")

    if app.config["UPDATE_PROGRAMME"]:
        # make sure we always do one at startup, but don't block server
        def do_initial_fetch():
            update_acts()
            update_act_descriptions()
            global acts
            global acts_lock
            with acts_lock:
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
        # pre-add days to ensure correct order
        for day in ("woensdag", "donderdag", "vrijdag", "zaterdag", "zondag"):
            acts_by_day[day] = {}

        def compare_show_times(act1, act2):
            """Compare show times, assuming next day at 06:00 instead of midnight"""
            start1 = act1[1]["shows"][0]["start"]
            start2 = act2[1]["shows"][0]["start"]

            if start1 == start2:
                return 0

            next_festival_day = "06:00"
            if start1 < start2:
                if start1 < next_festival_day and start2 >= next_festival_day:
                    # greater than (because one show is past midnight,
                    # but still same evening)
                    return 1
                return -1
            elif start1 > start2:
                if start1 >= next_festival_day and start2 < next_festival_day:
                    # lesser than (because one show is past midnight,
                    # but still same evening)
                    return -1
                return 1

        acts = OrderedDict(sorted(programme["acts"].items(),
                           key=cmp_to_key(compare_show_times)))

        for key, act in acts.items():
            for show in act["shows"]:
                day = show["day"]
                if key not in acts_by_day[day]:
                    assert day in acts_by_day
                    acts_by_day[day][key] = act.copy()

        fetch_time = programme.get("fetch_time", None)
        if fetch_time is not None:
            fetch_time = datetime.datetime.fromisoformat(programme["fetch_time"])
        else:
            fetch_time = None

        dev_mode_display = "block" if "devMode" in request.args else "none"

        free_fields = []
        return render_template("index.html", acts_by_day=acts_by_day,
                               dev_mode_display=dev_mode_display,
                               version=get_version(), fetch=fetch_time,
                               free_fields=free_fields)

    @app.route("/programme")
    def serve_programme():
        programme = make_legacy_programme("AMIGO")
        response = make_response(programme)
        return response

    def make_legacy_programme(stage=None):
        global acts
        global acts_lock
        global programme
        global programme_lock
        with acts_lock, programme_lock:
            legacy_programme = programme.copy()
            legacy_acts = legacy_programme["acts"]
            for act in acts:
                key = str(act["id"])
                legacy_act = legacy_acts.get(key, {})
                legacy_act["name"] = act["name"]
                shows = []
                legacy_act["shows"] = shows
                timeline: list[dict[str]] = act["timeline"]
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
        days = request.args.get("days", "donderdag;vrijdag;zaterdag;zondag").split(";")
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
                        return Response(
                            f"Timestamp key '{e.args[0]}' doesn't exist", status=400)

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

        global itinerary
        global itinerary_lock
        with itinerary_lock:
            if act_key not in itinerary:
                return Response("Act does not exist", status=404)
            itinerary[act_key][item] = request.data.decode("utf-8")
            persist_itinerary(itinerary)
        return "success"

    @app.route("/itinerary")
    def serve_dressing_rooms():
        return make_legacy_itinerary()

    def make_legacy_itinerary():
        global itinerary
        global itinerary_lock
        global acts
        global acts_lock
        with itinerary_lock, acts_lock:
            full_itinerary = itinerary.copy()

            for act in acts:
                key = str(act["id"])
                itin_item = full_itinerary.get(key, {})
                for event in act["timeline"]:
                    eventtype = event["type"]
                    if eventtype in LEGACY_ITINERARY_KEYS:
                        itin_item[LEGACY_ITINERARY_KEYS[eventtype]] = act_datestr_to_legacy_time(event["start"])

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
            if request.form["username"] == user.username and \
                    request.form["password"] == user.password:
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
    shifted_timestamp = timepoint.timestamp() - 6 * 3600
    return datetime.datetime.fromtimestamp(shifted_timestamp).weekday()
