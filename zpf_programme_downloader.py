#!/usr/bin/env python3

"""Parses the ZPF online programme and generates a CSV file from it, and downloads the images
"""

import os
import sys
import argparse
import requests
import json
import hashlib
from cachecontrol import CacheControl
from cachecontrol.caches.file_cache import FileCache

import calendar
from cachecontrol.heuristics import BaseHeuristic
from datetime import datetime, timedelta
from email.utils import parsedate, formatdate

import zpfwebsite

ZPF_URL = 'http://www.zomerparkfeest.nl'
BLOCK_DIAGRAM_BASE_URL = ZPF_URL + '/programma/schema/'

TMP_DIR = '/tmp/zpf_newsstand'
CACHE_DIR = TMP_DIR + '/requests_cache'
FORCED_CACHE_MARKER = TMP_DIR + '/forced_cache'


_parser = argparse.ArgumentParser(description=__doc__,
                                  formatter_class=argparse.ArgumentDefaultsHelpFormatter)


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
    _parser.add_argument('--force-cache',
                         help='cache ZPF website responses for some time, regardless of cache control headers (for faster testing)',
                         action='store_true')

    args = _parser.parse_args(argv)

    cache_dir = CACHE_DIR
    if args.force_cache:
        cache_dir += '_DEV'
    if not os.path.exists(cache_dir):
        os.makedirs(cache_dir)

    if args.stage_filter:
        print(f'warning: will only get stages: {", ".join(args.stage_filter)}')

    website = zpfwebsite.Website(args.force_cache)
    programme = website.get_programme(args.stage_filter)

    for name, act in programme.items():
        safename = name.encode('ascii', errors='ignore')
        act_dirname = hashlib.sha1(name.encode('utf8')).hexdigest()
        act_path = os.path.join(args.output_dir, act_dirname)
        if not os.path.exists(act_path):
            os.makedirs(act_path)

        if "img_src" not in act:
            continue

        print('getting image for act {}'.format(safename))
        image_data = website.session.get(act['img_src']).content
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
            print('(re)writing image for act {}'.format(safename))
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

    print('writing json')
    with open(os.path.join(args.output_dir, args.output_name + '.json'), 'w') as f:
        json.dump(programme, f, indent=2, separators=(',', ': '))

    print('KTHXBYE')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
