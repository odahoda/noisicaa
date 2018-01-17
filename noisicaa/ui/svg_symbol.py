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

import io
import logging
import os.path
import sys
from xml.etree import ElementTree

from PyQt5 import QtCore
from PyQt5.QtSvg import QSvgRenderer, QGraphicsSvgItem
from PyQt5.QtWidgets import QGraphicsItemGroup

from noisicaa.constants import DATA_DIR
from noisicaa import utils

logger = logging.getLogger(__name__)

namespaces = {
    'dc': 'http://purl.org/dc/elements/1.1/',
    'cc': 'http://creativecommons.org/ns#',
    'rdf': 'http://www.w3.org/1999/02/22-rdf-syntax-ns#',
    'svg': 'http://www.w3.org/2000/svg',
    'sodipodi': 'http://sodipodi.sourceforge.net/DTD/sodipodi-0.dtd',
    'inkscape': 'http://www.inkscape.org/namespaces/inkscape',
    'noisicaa': 'http://noisicaa.odahoda.de/xmlns/svg-symbol',
    }

for prefix, url in namespaces.items():
    ElementTree.register_namespace(prefix, url)


def _fqattr(ns, attr):
    return '{%s}%s' % (namespaces[ns], attr)


class SvgSymbol(object):
    _cache = {}

    def __init__(self, path):
        self._path = path
        if not os.path.isfile(self._path):
            raise FileNotFoundError(self._path)

    @utils.memoize
    def get_dom(self):
        return ElementTree.parse(io.BytesIO(self.get_xml()))

    @utils.memoize
    def get_xml(self):
        with open(self._path, 'rb') as fp:
            return fp.read()

    def get_origin(self):
        tree = self.get_dom()
        root = tree.getroot()

        origin_x = float(root.get(_fqattr('noisicaa', 'origin-x'), '0'))
        origin_y = float(root.get(_fqattr('noisicaa', 'origin-y'), '0'))
        return (origin_x, origin_y)

    @utils.memoize
    def get_renderer(self):
        return QSvgRenderer(self.get_xml())

    @classmethod
    def get(cls, symbol_name):
        try:
            svg_symbol = cls._cache[symbol_name]
        except KeyError:
            path = os.path.join(DATA_DIR, 'symbols', '%s.svg' % symbol_name)
            svg_symbol = SvgSymbol(path)
            cls._cache[symbol_name] = svg_symbol

        return svg_symbol


def paintSymbol(painter, symbol_name, pos):
    sym = SvgSymbol.get(symbol_name)
    sym_renderer = sym.get_renderer()
    origin_x, origin_y = sym.get_origin()
    box = QtCore.QRectF(
        QtCore.QPointF(-origin_x, -origin_y),
        sym_renderer.viewBoxF().size() * 0.5)
    sym_renderer.render(
        painter,
        box.translated(pos))


class SymbolItem(QGraphicsItemGroup):
    _cache = {}

    def __init__(self, symbol, parent=None):
        super().__init__(parent)

        self._symbol = symbol

        try:
            renderer, svg_symbol = self._cache[self._symbol]
        except KeyError:
            path = os.path.join(DATA_DIR, 'symbols', '%s.svg' % self._symbol)
            svg_symbol = SvgSymbol(path)
            renderer = QSvgRenderer(svg_symbol.get_xml())
            self._cache[self._symbol] = (renderer, svg_symbol)

        self.grp = QGraphicsItemGroup(self)
        origin_x, origin_y = svg_symbol.get_origin()
        self.grp.setPos(-origin_x, -origin_y)

        self.body = QGraphicsSvgItem(self.grp)
        self.body.setSharedRenderer(renderer)

        # FIXME: conditionally enable bounding boxes
        #box = QtWidgets.QGraphicsRectItem(self.grp)
        #box.setRect(self.body.boundingRect())


if __name__ == '__main__':  # pragma: no cover
    sym = SvgSymbol(sys.argv[1])
    print(sym.get_xml().decode('utf-8'))
