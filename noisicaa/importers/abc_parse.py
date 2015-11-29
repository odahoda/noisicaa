#!/usr/bin/python3

import argparse
import logging
import os.path
import pprint
import sys

if __name__ == '__main__':
    import pyximport
    pyximport.install()

from noisicaa import music
from . import abc

def main(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument('paths', type=str, nargs='+')
    parser.add_argument('--debug', action='store_true')
    parser.add_argument('--dump', action='store_true')
    args = parser.parse_args(argv[1:])

    if args.debug:
        logging.basicConfig(level=logging.DEBUG)

    for path in args.paths:
        p = music.Project()
        importer = abc.ABCImporter()
        importer.import_file(path, p)
        if args.dump:
            pprint.pprint(p.serialize())


if __name__ == '__main__':
    main(sys.argv)
