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

# import logging

# from noisidev import unittest
# from . import builtin_scanner
# from . import preset_scanner

# logger = logging.getLogger(__name__)


# class PresetScannerTest(unittest.TestCase):
#     def setup_testcase(self):
#         scanner = builtin_scanner.BuiltinScanner()
#         self.nodes = dict(scanner.scan())

#     def test_scan(self):
#         scanner = preset_scanner.PresetScanner(self.nodes)
#         for uri, _ in scanner.scan():
#             logger.info(uri)
