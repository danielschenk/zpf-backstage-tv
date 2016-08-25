#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Flask app which serves as the backend for the Zomerparkfeest newsstand

:author: dansch
"""

import socket
import requests
import os
import time
from lxml import html
import urlparse

from flask import Flask, render_template, jsonify, g, make_response

ZPF_URL = 'http://www.zomerparkfeest.nl'

app = Flask(__name__)


def url_to_fs_path(url):
    scheme, netloc, path, parameters, query, fragment = urlparse.urlparse(url)

    components = path.split('/')
    if components[0] == '':
        components = components[1:]
    dirpath = ''
    for component in components[:-1]:
        dirpath += 'dir_' + component + '/'

    return os.path.join(app.instance_path, 'web_cache', scheme, netloc,
                        dirpath, components[-1])


def cache_resource(url, contents):
    fs_path = url_to_fs_path(url)
    dirname = os.path.dirname(fs_path)
    if not os.path.exists(dirname):
        os.makedirs(dirname)
    with open(fs_path, 'wb') as f:
        f.write(contents)


def get_resource(url):
    need_update = False

    try:
        cache_path = url_to_fs_path(url)
        if time.time() - os.path.getmtime(cache_path) < 3600:
            with open(cache_path, 'rb') as f:
                print 'using resource {0} from cache'.format(url.encode('ascii', 'replace'))
                contents = f.read()
        else:
            need_update = True
    except (OSError, IOError):
        need_update = True

    if need_update:
        print 'fetching resource {0}...'.format(url.encode('ascii', 'replace'))
        contents = requests.get(url).content
        cache_resource(url, contents)

    return contents


def parse_program_az(az_html):
    tree = html.fromstring(az_html)
    acts = tree.xpath("//div[contains(concat(' ', @class, ' '), ' act ')]")
    programme = []
    for act in acts:
        img = act.find("figure/picture//img")
        a = act.find("figure/figcaption/a")
        actinfo = {}
        actinfo['name'] = a.text
        actinfo['url'] = a.get('href')
        actinfo['img_src'] = img.get('data-src')

        act_html = get_resource(actinfo['url'])
        tree_act = html.fromstring(act_html)
        div_playdate = tree_act.xpath(
            "//div[@class='playDate']")
        div_desc = tree_act.xpath(
            "//div[contains(concat(' ', @class, ' '), ' content ')]")

        actinfo['description'] = div_desc[0].find("p").text

        print div_playdate[0].findall("span")
        actinfo['stage'] = div_playdate[0].findall("span")[1].text

        programme.append(actinfo)
    return programme


@app.route("/")
def serve_index():
    """Main page handler"""
    
    hostname = socket.gethostname()
    return render_template('index.html', **locals())


@app.route("/programme")
def serve_program():
    response = make_response(jsonify(parse_program_az(get_resource(ZPF_URL + '/programma/a-z'))))
    return response

