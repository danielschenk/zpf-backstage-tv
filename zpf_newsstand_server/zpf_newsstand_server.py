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
from lxml import html
import pprint

from flask import Flask, render_template, jsonify, g, make_response

ZPF_URL = 'http://www.zomerparkfeest.nl'

app = Flask(__name__)


def get_resource(url, session):
    contents = session.get(url).content

    return contents


def parse_program_az(az_html, session):
    tree = html.fromstring(az_html)
    acts = tree.xpath("//div[contains(concat(' ', @class, ' '), ' act ')]")
    programme = []
    act_number = 1
    for act in acts:
        img = act.find("figure/picture//img")
        a = act.find("figure/figcaption/a")
        actinfo = {}
        actinfo['name'] = a.text
        actinfo['url'] = a.get('href')
        actinfo['img_src'] = img.get('data-src')

        print u'getting and parsing page for act {}/{} "{}"'.format(act_number, len(acts), actinfo['name'])
        act_html = get_resource(actinfo['url'], session)
        tree_act = html.fromstring(act_html)
        div_playdate = tree_act.xpath(
            "//div[@class='playDate']")
        div_content = tree_act.xpath(
            "//div[contains(concat(' ', @class, ' '), ' content ')]")

        if div_playdate and div_content:
            paragraphs = []
            for element in div_content[0].iter():
                if element.tag.lower() == 'p':
                    # get the contents of this <p> element as-is, ie. a string with all child elements unparsed
                    text = u''.join([element.text if element.text else ''] + [html.tostring(e) for e in element.getchildren()])
                    paragraphs.append(text)

            actinfo['description'] = '<p>' + '</p><p>'.join(paragraphs) + '</p>'
            actinfo['stage'] = div_playdate[0].findall("span")[1].text

            programme.append(actinfo)
        else:
            print u'unexpected structure in page of act "{}", skipping'.format(actinfo['name'])

        act_number += 1

    pprint.pprint(programme)

    return programme


@app.route("/")
def serve_index():
    """Main page handler"""
    
    hostname = socket.gethostname()
    return render_template('index.html', **locals())


@app.route("/programme")
def serve_program():
    session = CacheControl(requests.Session(),
                           cache=FileCache(os.path.join(app.instance_path, 'requests_cache')))
    response = make_response(jsonify(parse_program_az(get_resource(ZPF_URL + '/programma/a-z', session), session)))
    return response
