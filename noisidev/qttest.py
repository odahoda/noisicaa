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
import concurrent.futures
import logging
import sys
import traceback

from PyQt5 import QtWidgets
import quamash

from noisicaa import constants
from . import unittest

logger = logging.getLogger(__name__)


def error_handler(event_loop, context):
    try:
        event_loop.default_exception_handler(context)
    except:  # pylint: disable=bare-except
        traceback.print_exc()

    try:
        msg = context['message']
        exc = context.get('exception', None)
        if exc is not None:
            tb = exc.__traceback__
            if tb is not None:
                msg += '\n%s' % ''.join(traceback.format_exception(type(exc), exc, tb))
            else:
                msg += '\n%s: %s\nNo traceback' % (type(exc).__name__, exc)
        src_tb = context.get('source_traceback', None)
        if src_tb is not None:
            msg += '\nSource Traceback:\n%s' % ''.join(traceback.format_list(src_tb))
        sys.stderr.write(msg)

    except:  # pylint: disable=bare-except
        traceback.print_exc()


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

        event_loop = quamash.QEventLoop(cls.qt_app)
        event_loop.set_exception_handler(error_handler)
        asyncio.set_event_loop(event_loop)
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=10)
        event_loop.set_default_executor(executor)

    def setup_testcase(self):
        if not constants.TEST_OPTS.ALLOW_UI:
            raise unittest.SkipTest("QT tests disabled")
