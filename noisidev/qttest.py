#!/usr/bin/python3

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

import asyncio
import functools
import inspect
import logging
import os.path

from PyQt5 import QtWidgets
import asynctest
import quamash

from noisicaa import constants
from . import unittest

logger = logging.getLogger(__name__)


class QtTestCase(unittest.AsyncTestCase):
    use_default_loop = True
    qt_app = None  # type: QtWidgets.QApplication

    @classmethod
    def setUpClass(cls):
        if not constants.TEST_OPTS.ALLOW_UI:
            return

        if cls.qt_app is None:
            cls.qt_app = QtWidgets.QApplication(['unittest'])
            cls.qt_app.setQuitOnLastWindowClosed(False)

        asyncio.set_event_loop(quamash.QEventLoop(cls.qt_app))

    @classmethod
    def tearDownClass(cls):
        asyncio.set_event_loop(None)

    def setup_testcase(self):
        if not constants.TEST_OPTS.ALLOW_UI:
            raise unittest.SkipTest("QT tests disabled")
