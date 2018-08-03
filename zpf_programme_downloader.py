#!/usr/bin/env python

"""Parses the ZPF online programme and generates a CSV file from it, and downloads the images
"""

import os
import shutil
import sys
import argparse
import requests
import csv
import json
import hashlib
from cachecontrol import CacheControl
from cachecontrol.caches.file_cache import FileCache

import calendar
from cachecontrol.heuristics import BaseHeuristic
from datetime import datetime, timedelta
from email.utils import parsedate, formatdate

import zpfwebsite.parser

ZPF_URL = 'http://www.zomerparkfeest.nl'
PROGRAMME_AZ_URL = ZPF_URL + '/programme/a-z'

TMP_DIR = '/tmp/zpf_newsstand'
CACHE_DIR = TMP_DIR + '/requests_cache'
FORCED_CACHE_MARKER = TMP_DIR + '/forced_cache'


_parser = argparse.ArgumentParser(description=__doc__,
                                  formatter_class=argparse.ArgumentDefaultsHelpFormatter)


# Example from cachecontrol documentation
class OneWeekHeuristic(BaseHeuristic):

    def update_headers(self, response):
        date = parsedate(response.headers['date'])
        expires = datetime(*date[:6]) + timedelta(weeks=1)
        return {
            'expires' : formatdate(calendar.timegm(expires.timetuple())),
            'cache-control' : 'public',
        }

    def warning(self, response):
        msg = 'Automatically cached! Response is Stale.'
        return '110 - "%s"' % msg


def main(argv):
    _parser.add_argument('--output-dir',
                         help='path to directory where to store output in',
                         default='programme')
    _parser.add_argument('--output-name',
                         help='name of the generated csv and json',
                         default='programme')
    _parser.add_argument('--stage-filter',
                         help='list of stages to select, omit to get all stages',
                         nargs='+',
                         metavar='STAGENAME',
                         default=None)
    _parser.add_argument('--source',
                         help='URL of the a-z programme page',
                         default=PROGRAMME_AZ_URL)
    _parser.add_argument('--merge-csv',
                         help='csv file with extra columns to merge, act name is the key')
    _parser.add_argument('--force-cache',
                         help='cache ZPF website responses for some time, regardless of cache control headers (for faster testing)',
                         action='store_true')

    args = _parser.parse_args(argv)

    if args.force_cache:
        open(FORCED_CACHE_MARKER, 'a').close()
    else:
        if os.path.exists(FORCED_CACHE_MARKER):
            print 'cleaning the cache because it was forced before'
            shutil.rmtree(CACHE_DIR)
            os.unlink(FORCED_CACHE_MARKER)

    if not os.path.exists(CACHE_DIR):
        os.makedirs(CACHE_DIR)

    session = CacheControl(requests.Session(),
                           cache=FileCache(CACHE_DIR),
                           heuristic=OneWeekHeuristic() if args.force_cache else None)

    programme_az_html = session.get(PROGRAMME_AZ_URL).content
    programme = zpfwebsite.parser.parse_program_az(programme_az_html, session)
    filtered_programme = {}

    stages = [stage.lower() for stage in args.stage_filter] if args.stage_filter else None
    for name, act in programme.iteritems():
        if stages is None or (act['stage'] and act['stage'].lower() in stages):
            filtered_programme[name] = act

    for name, act in filtered_programme.iteritems():
        act_dirname = hashlib.sha1(name.encode('utf8')).hexdigest()
        act_path = os.path.join(args.output_dir, act_dirname)
        if not os.path.exists(act_path):
            os.makedirs(act_path)

        print u'getting image for act {}'.format(name)
        image_data = session.get(act['img_src']).content
        relative_image_path = os.path.join(act_dirname, os.path.basename(act['img_src']))
        image_path = os.path.join(act_path, os.path.basename(act['img_src']))
        write = False
        if os.path.exists(image_path):
            with open(image_path, 'rb') as f:
                old_image_data = f.read()
                if old_image_data != image_data:
                    write = True
        else:
            write = True
        if write:
            print u'(re)writing image for act {}'.format(name)
            with open(image_path, 'wb') as f:
                f.write(image_data)
        # Image path relative to csv
        act['image'] = relative_image_path

        day_map = {
            'do': 'donderdag',
            'vr': 'vrijdag',
            'za': 'zaterdag',
            'zo': 'zondag',
        }
        act['dag'] = day_map[act['day'].lower()]

    if not os.path.exists(args.output_dir):
        os.makedirs(args.output_dir)

    if args.merge_csv:
        with open(args.merge_csv, 'r') as f:
            reader = csv.DictReader(f)
            for line in reader:
                if line['name'] in filtered_programme:
                    filtered_programme[line['name']].update(line)

    with open(os.path.join(args.output_dir, args.output_name + '.json'), 'w') as f:
        json.dump(filtered_programme, f, indent=4, separators=(',', ': '))

    with open(os.path.join(args.output_dir, args.output_name + '.csv'), 'w') as f:
        writer = csv.DictWriter(f, ['dag','name','genre','getin','dressingroom','soundcheck','linecheck','showtime','end','country','image','description','local'],
                                extrasaction='ignore')
        writer.writeheader()
        for k, v in filtered_programme.iteritems():
            writer.writerow({k: v.encode('utf8') for k, v in v.iteritems()})

    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
