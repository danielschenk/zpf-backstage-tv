#!/usr/bin/env python3

"""Flask app which serves as the backend for the Zomerparkfeest Amigo backstage TV"""

import threading
import json
import datetime
import subprocess
import pathlib
from typing import Mapping, OrderedDict
from functools import cmp_to_key
import os
from dataclasses import dataclass
from urllib.parse import urlparse, urljoin
import flask
from flask import Flask, render_template, jsonify, make_response, request, Response
from flask_login import LoginManager, login_user, login_required
from flask_bootstrap import Bootstrap
from src import users
from apscheduler.schedulers.background import BackgroundScheduler
import icalendar

import zpfwebsite.errors


APP_DIR = pathlib.Path(__file__).parent
DEFAULT_INSTANCE_PATH = APP_DIR / "instance"

programme = {
    "acts": {}
}
programme_lock = threading.Lock()

itinerary = {}
itinerary_lock = threading.Lock()

scheduler = BackgroundScheduler()


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

    _key = app.config["SECRET_KEY"]
    if _key is None:
        print("WARNING: SECRET_KEY not set, using random key every restart!")
        _key = os.urandom(64)
    app.config["SECRET_KEY"] = _key

    login_manager = LoginManager()
    login_manager.init_app(app)
    Bootstrap(app)

    def persist_itinerary(itinerary):
        with app.open_instance_resource("itinerary.json", "w+") as f:
            json.dump(itinerary, f, indent=2)

    def initialize_nonexistent_act_itineraries(acts):
        global itinerary
        global itinerary_lock
        with itinerary_lock:
            for key in acts:
                if key not in itinerary:
                    itinerary[key] = {"dressing_room": "None"}
            persist_itinerary(itinerary)

    def update_programme_cache():
        website = zpfwebsite.Website()
        programme_temp = website.get_programme(stage_list=["AMIGO"])
        add_show_timestamps(programme_temp["acts"])
        global programme
        global programme_lock
        with programme_lock:
            programme = programme_temp.copy()
        with app.open_instance_resource("programme_cache.json", "w+") as f:
            json.dump(programme_temp, f, indent=2)

        initialize_nonexistent_act_itineraries(programme_temp["acts"])

    try:
        global programme
        with app.open_instance_resource("programme_cache.json", "r") as f:
            print("found programme cache on disk")
            programme = json.load(f)
            try:
                major, minor = programme["schema_version"].split(".")
                if major == 0 and minor < 2:
                    raise IncompatibleCacheError()
            except KeyError:
                raise IncompatibleCacheError()
            add_show_timestamps(programme["acts"])
    except (FileNotFoundError, IncompatibleCacheError):
        print("no programme cache on disk or incompatible, need initial fetch")
        try:
            update_programme_cache()
        except zpfwebsite.errors.ZpfWebsiteError as e:
            print(f"error: {e}")

    try:
        global itinerary
        with app.open_instance_resource("itinerary.json", "r") as f:
            print("found persisted itinerary on disk")
            itinerary = json.load(f)
    except FileNotFoundError:
        print("no itinerary on disk")

    initialize_nonexistent_act_itineraries(programme["acts"])

    if app.config["UPDATE_PROGRAMME"]:
        scheduler.add_job(update_programme_cache, "interval", minutes=30)
        scheduler.start()

    @app.route("/")
    @login_required
    def serve_index():
        """Main page handler"""
        with programme_lock:
            acts_by_day = OrderedDict()
            # pre-add days to ensure correct order
            for day in ("donderdag", "vrijdag", "zaterdag", "zondag"):
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

        free_fields = [
            ItineraryField("get_in", "Get-in", "time"),
            ItineraryField("soundcheck", "Soundcheck", "time"),
            ItineraryField("linecheck", "Linecheck", "time"),
        ]
        return render_template("index.html", acts_by_day=acts_by_day,
                               dev_mode_display=dev_mode_display,
                               version=get_version(), fetch=fetch_time,
                               free_fields=free_fields)

    @app.route("/programme")
    def serve_programme():
        global programme
        global programme_lock
        with programme_lock:
            response = make_response(jsonify(programme))
        return response

    @app.route("/programme.ics")
    def serve_ical():
        cal = icalendar.Calendar()
        cal.add("PRODID", "-//amigotext//NONSGML amigotext.app.event//EN")
        cal.add("VERSION", "2.0")
        hostname = urlparse(request.base_url).hostname
        global programme
        global programme_lock
        with programme_lock:
            fetch_time = datetime.datetime.fromisoformat(programme["fetch_time"])
            for key, act in programme["acts"].items():
                for show in act["shows"]:
                    event = icalendar.Event()
                    event.add("DTSTART",
                        datetime.datetime.fromtimestamp(show["start_utc"], datetime.UTC))
                    event.add("DTEND",
                        datetime.datetime.fromtimestamp(show["end_utc"], datetime.UTC))
                    event.add("LAST-MODIFIED", fetch_time)
                    event.add("UID", f"{key}@{hostname}")
                    event.add("SUMMARY", act["name"])
                    event.add("DESCRIPTION", f"{act['description']}\n\n{act['url']}")
                    event.add("LOCATION", show["stage"])
                    cal.add_component(event)

        return Response(cal.to_ical(), mimetype="text/calendar")

    @app.route("/itinerary/<act_key>", methods=["GET"])
    def serve_dressing_room(act_key):
        global itinerary
        global itinerary_lock
        with itinerary_lock:
            if act_key not in itinerary:
                return Response("Act does not exist", status=404)

            return jsonify(itinerary[act_key])

    @app.route("/itinerary/<act_key>/<item>", methods=["PUT"])
    @login_required
    def update_dressing_room(act_key, item):
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
        global itinerary
        global itinerary_lock
        with itinerary_lock:
            return jsonify(itinerary)

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


def hour_minute(time: str):
    return int(time[0:2]), int(time[3:5])


def add_show_timestamps(acts: Mapping):
    year = datetime.datetime.now().year
    for act in acts.values():
        for show in act["shows"]:
            start_day = end_day = show["day_of_month"]
            # in programme, past-midnight shows show same day
            # but in real time it is the next
            if show["start"].startswith("0"):
                start_day += 1
            if show["end"].startswith("0"):
                end_day += 1
            hour, minute = hour_minute(show["start"])
            start = datetime.datetime(year, 8, start_day, hour, minute)
            hour, minute = hour_minute(show["end"])
            end = datetime.datetime(year, 8, end_day, hour, minute)

            show["start_utc"] = int(start.timestamp())
            show["end_utc"] = int(end.timestamp())
