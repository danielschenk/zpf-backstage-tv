#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Flask app which serves as the backend for the Zomerparkfeest newsstand

:author: dansch
"""

import socket
import requests
from cachecontrol import CacheControl
from cachecontrol.caches.file_cache import FileCache
import os
from flask import Flask, render_template, jsonify, g, make_response

import zpfwebsite.parser

ZPF_URL = 'http://www.zomerparkfeest.nl'

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
def serve_program():
    session = CacheControl(requests.Session(),
                           cache=FileCache(os.path.join(app.instance_path, 'requests_cache')))
    response = make_response(jsonify(zpfwebsite.parser.parse_program_az(get_resource(ZPF_URL + '/programma/a-z', session), session)))
    return response
