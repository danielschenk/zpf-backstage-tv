#!/usr/bin/env python3

"""Flask app which serves as the backend for the Zomerparkfeest Amigo backstage TV"""

import threading
import pickle
from typing import OrderedDict
from functools import cmp_to_key
from flask import Flask, render_template, jsonify, make_response, request
from apscheduler.schedulers.background import BackgroundScheduler

import zpfwebsite

programme = {}
programme_lock = threading.Lock()

rooms = {}
rooms_lock = threading.Lock()

app = Flask(__name__)


def get_resource(url, session):
    contents = session.get(url).content

    return contents


@app.route("/")
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

    return render_template("index.html", acts_by_day=acts_by_day)


@app.route("/programme")
def serve_programme():
    with programme_lock:
        response = make_response(jsonify(programme))
    return response


@app.route("/dressing_rooms/<act_key>", methods=["GET"])
def serve_dressing_room(act_key):
    with rooms_lock:
        if act_key in rooms:
            return str(rooms[act_key])
        else:
            return "None"


@app.route("/dressing_rooms/<act_key>", methods=["PUT"])
def update_dressing_room(act_key):
    with rooms_lock:
        rooms[act_key] = request.data.decode("utf-8")
    return "success"


@app.route("/dressing_rooms")
def serve_dressing_rooms():
    with rooms_lock:
        return jsonify(rooms)


def update_programme_cache():
    website = zpfwebsite.Website()
    programme_temp = website.get_programme(stage_list=["AMIGO"])
    with programme_lock:
        global programme
        programme = programme_temp.copy()
    with app.open_instance_resource("programme_cache.pickle", "wb+") as f:
        pickle.dump(programme_temp, f)


try:
    with app.open_instance_resource("programme_cache.pickle", "rb") as f:
        print("found programme cache on disk")
        programme = pickle.load(f)
except FileNotFoundError:
    print("no programme cache on disk, need initial fetch")
    update_programme_cache()


scheduler = BackgroundScheduler()
scheduler.add_job(update_programme_cache, "interval", minutes=15)
scheduler.start()
