#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Flask app which serves as the backend for the Zomerparkfeest newsstand

:author: dansch
"""

import socket
import requests
import os
import time
import xml.etree.ElementTree as ET

from flask import Flask, render_template, jsonify, g, make_response

ZPF_URL = 'http://www.zomerparkfeest.nl'

app = Flask(__name__)


def zpf_to_fs_path(path):
    if path.startswith('/'):
        path = path[1:]
    components = path.split('/')
    dirpath = ''
    for component in components[:-1]:
        dirpath += 'dir_' + component + '/'

    return os.path.join(app.instance_path, 'zpf_cache', dirpath,
                        components[-1])


def cache_zpf_resource(path, contents):
    if path.startswith('/'):
        path = path[1:]
    fs_path = zpf_to_fs_path(path)
    dirname = os.path.dirname(fs_path)
    if not os.path.exists(dirname):
        os.makedirs(dirname)
    with open(fs_path, 'wb') as f:
        f.write(contents.encode('utf-8'))


def get_zpf_resource(path):
    need_update = False

    try:
        cache_path = zpf_to_fs_path(path)
        if time.time() - os.path.getmtime(cache_path) < 3600:
            with open(cache_path, 'rb') as f:
                print 'serving {0} from cache'.format(path)
                contents = f.read().decode('utf-8')
        else:
            need_update = True
    except (OSError, IOError):
        need_update = True

    if need_update:
        contents = requests.get(ZPF_URL + path).text
        cache_zpf_resource(path, contents)

    return contents


def parse_program_az(az_html):
    root = ET.fromstring(az_html)
    acts = root.findall("//div[contains(concat(' ', @class, ' '), ' act ')]")
    return acts


@app.route("/")
def serve_index():
    """Main page handler"""
    
    hostname = socket.gethostname()
    return render_template('index.html', **locals())


@app.route("/program")
def serve_program():
    response = parse_program_az(get_zpf_resource('/programma/a-z'))
    return response

