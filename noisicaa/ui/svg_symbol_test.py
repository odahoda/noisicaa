#/usr/bin/python3

# @begin:license
#
# Copyright (c) 2015-2019, Benjamin Niemann <pink@odahoda.de>
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

import os.path
from xml.etree.ElementTree import ElementTree

from noisidev import unittest
from . import svg_symbol


class SvgSymbolTest(unittest.TestCase):
    def test_orig_not_found(self):
        with self.assertRaises(FileNotFoundError):
            svg_symbol.SvgSymbol('/does-not-exist')

    def test_get_dom(self):
        sym = svg_symbol.SvgSymbol(os.path.join(unittest.TESTDATA_DIR, 'symbol.svg'))
        dom = sym.get_dom()
        self.assertIsInstance(dom, ElementTree)

    def test_get_xml(self):
        sym = svg_symbol.SvgSymbol(os.path.join(unittest.TESTDATA_DIR, 'symbol.svg'))
        xml1 = sym.get_xml()
        self.assertIsInstance(xml1, bytes)

    def test_get_origin(self):
        sym = svg_symbol.SvgSymbol(os.path.join(unittest.TESTDATA_DIR, 'symbol.svg'))
        ox, oy = sym.get_origin()
        self.assertIsInstance(ox, float)
        self.assertIsInstance(oy, float)


class SymbolItemTest(unittest.TestCase):
    def test_init(self):
        item = svg_symbol.SymbolItem('rest-quarter')
        bbox = item.body.boundingRect()
        self.assertGreater(bbox.width(), 0)
        self.assertGreater(bbox.height(), 0)
