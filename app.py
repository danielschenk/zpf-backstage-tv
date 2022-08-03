#!/usr/bin/env python3

"""Flask app which serves as the backend for the Zomerparkfeest Amigo backstage TV"""

import socket
import threading
import pickle
import os
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
        return render_template("index.html", acts=programme["acts"])


@app.route("/programme")
def serve_programme():
    with programme_lock:
        response = make_response(jsonify(programme))
    return response


@app.route("/dressing_room/<act_key>", methods=["GET"])
def serve_dressing_room(act_key):
    with rooms_lock:
        if act_key in rooms:
            return str(rooms[act_key])
        else:
            return "None"


@app.route("/dressing_room/<act_key>", methods=["PUT"])
def update_dressing_room(act_key):
    with rooms_lock:
        rooms[act_key] = request.data.decode("utf-8")
    return "success"


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
