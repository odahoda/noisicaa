#/usr/bin/python3

# @begin:license
#
# Copyright (c) 2015-2017, Benjamin Niemann <pink@odahoda.de>
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
import unittest
import tempfile
import shutil
from unittest import mock
from xml.etree.ElementTree import ElementTree

from . import svg_symbol

TESTDATA_DIR = os.path.join(os.path.dirname(__file__), 'testdata')


class SvgSymbolTest(unittest.TestCase):
    def setUp(self):
        self.cache_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.cache_dir)

    def test_orig_not_found(self):
        with self.assertRaises(FileNotFoundError):
            svg_symbol.SvgSymbol('/does-not-exist')

    def test_get_dom(self):
        sym = svg_symbol.SvgSymbol(
            os.path.join(TESTDATA_DIR, 'symbol.svg'),
            cache_dir=self.cache_dir)
        dom = sym.get_dom()
        self.assertIsInstance(dom, ElementTree)

    def test_get_xml(self):
        sym = svg_symbol.SvgSymbol(
            os.path.join(TESTDATA_DIR, 'symbol.svg'),
            cache_dir=self.cache_dir)
        xml1 = sym.get_xml()
        self.assertIsInstance(xml1, bytes)
        self.assertTrue(
            os.path.isfile(os.path.join(self.cache_dir, 'symbol.stripped.svg')))

        # No load it again. This time we should load it from the cached path.
        sym = svg_symbol.SvgSymbol(
            os.path.join(TESTDATA_DIR, 'symbol.svg'),
            cache_dir=self.cache_dir)
        sym.strip_dom = mock.MagicMock()
        xml2 = sym.get_xml()
        self.assertFalse(sym.strip_dom.called)

        self.assertEqual(xml1, xml2)

    def test_get_origin(self):
        sym = svg_symbol.SvgSymbol(
            os.path.join(TESTDATA_DIR, 'symbol.svg'),
            cache_dir=self.cache_dir)
        ox, oy = sym.get_origin()
        self.assertIsInstance(ox, float)
        self.assertIsInstance(oy, float)


class SymbolItemTest(unittest.TestCase):
    def setUp(self):
        self.cache_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.cache_dir)

    def test_init(self):
        item = svg_symbol.SymbolItem('rest-quarter', cache_dir=self.cache_dir)
        bbox = item.body.boundingRect()
        self.assertGreater(bbox.width(), 0)
        self.assertGreater(bbox.height(), 0)


if __name__ == '__main__':
    unittest.main()
