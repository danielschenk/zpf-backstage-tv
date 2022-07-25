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
app = Flask(__name__)


def get_resource(url, session):
    contents = session.get(url).content

    return contents


@app.route("/")
def serve_index():
    """Main page handler"""

    hostname = socket.gethostname()
    return render_template('index.html', **locals())


@app.route("/programme")
def serve_programme():
    with programme_lock:
        response = make_response(jsonify(programme))
    return response


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