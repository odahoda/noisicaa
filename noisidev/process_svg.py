#!/usr/bin/python3

# @begin:license
#
# Copyright (c) 2015-2018, Benjamin Niemann <pink@odahoda.de>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# @end:license

import argparse
import os.path
import re
import subprocess
import sys
import tempfile
from xml.etree import ElementTree

import cssutils


namespaces = {
    'dc': 'http://purl.org/dc/elements/1.1/',
    'cc': 'http://creativecommons.org/ns#',
    'rdf': 'http://www.w3.org/1999/02/22-rdf-syntax-ns#',
    'svg': 'http://www.w3.org/2000/svg',
    'sodipodi': 'http://sodipodi.sourceforge.net/DTD/sodipodi-0.dtd',
    'inkscape': 'http://www.inkscape.org/namespaces/inkscape',
    'noisicaa': 'http://noisicaa.odahoda.de/xmlns/svg-symbol',
    }


def _fqattr(ns, attr):
    return '{%s}%s' % (namespaces[ns], attr)


def main(argv):
    argparser = argparse.ArgumentParser(description='Preprocess SVG image.')
    argparser.add_argument('input', type=str)
    argparser.add_argument('--output', '-o', type=str, default=None)
    args = argparser.parse_args(argv[1:])

    for prefix, url in namespaces.items():
        ElementTree.register_namespace(prefix, url)

    tree = ElementTree.parse(args.input)
    root = tree.getroot()

    for grp in root.findall('svg:g', namespaces):
        if grp.get(_fqattr('inkscape', 'groupmode')) != 'layer':
            continue

        style = cssutils.parseStyle(grp.get('style', ''))
        if style.getProperty('display').value == 'none':
            root.remove(grp)
            continue

    elem = root.find('sodipodi:namedview', namespaces)
    if elem is not None:  # pragma: no branch
        root.remove(elem)

    elem = root.find('svg:metadata', namespaces)
    if elem is not None:  # pragma: no branch
        root.remove(elem)

    with tempfile.TemporaryDirectory() as tmpdirname:
        svgpath = os.path.join(tmpdirname, 'svg')
        with open(svgpath, 'wb') as fp:
            tree.write(fp, encoding='utf-8', xml_declaration=True)

        pngpath = os.path.join(tmpdirname, 'png')
        subprocess.check_call(['inkscape', svgpath, '-e', pngpath],
                              stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL)

        info = subprocess.check_output(
            ['convert', pngpath, '-trim', 'info:-'])
        info = info.decode('ascii')
        m = re.match(
            r'.* PNG (\d+)x(\d+) (\d+)x(\d+)\+(\d+)\+(\d+) .*$', info)
        assert m is not None, info
        width, height, canvas_width, canvas_height, xoffset, yoffset = [
            int(g) for g in m.groups()]
        xoffset -= 8
        yoffset -= 8
        width += 16
        height += 16

        root.set(
            'viewBox', '%d %d %d %d' % (xoffset, yoffset, width, height))
        root.set(
            _fqattr('noisicaa', 'origin-x'),
            '%f' % ((canvas_width / 2 - xoffset) / 2))
        root.set(
            _fqattr('noisicaa', 'origin-y'),
            '%f' % ((canvas_height / 2 - yoffset) / 2))
        root.set('width', '%f' % (width / 2))
        root.set('height', '%f' % (height / 2))

    if args.output is not None:
        with open(args.output, 'wb') as fp:
            tree.write(fp, encoding='utf-8', xml_declaration=True)
    else:
        tree.write(sys.stdout.buffer, encoding='utf-8', xml_declaration=True)

    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
