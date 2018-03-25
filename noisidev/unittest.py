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

import asyncio
import functools
import inspect
import logging
import os.path
import unittest

from PyQt5 import QtWidgets
import asynctest
import quamash

from noisicaa import constants

logger = logging.getLogger(__name__)

TESTDATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'testdata'))

skip = unittest.skip
skipIf = unittest.skipIf
skipUnless = unittest.skipUnless
expectedFailure = unittest.expectedFailure
TestSuite = unittest.TestSuite


KNOWN_TAGS = {'unit', 'lint', 'pylint', 'mypy', 'integration', 'perf'}

def tag(*tags):
    unknown_tags = set(tags) - KNOWN_TAGS
    assert not unknown_tags, unknown_tags

    def dec(func):
        if not hasattr(func, '_unittest_tags'):
            func._unittest_tags = set()

        func._unittest_tags.update(tags)
        return func

    return dec


class SetupTestCaseMixin(object):

    @property
    def tags(self):
        test_method = getattr(self, self._testMethodName)
        return getattr(test_method, '_unittest_tags', {'unit'})

    def _setup_testcase_methods(self):
        for cls in reversed(self.__class__.__mro__):
            try:
                setup_testcase = cls.__dict__['setup_testcase']
                logger.debug("Running %s.setup_testcase()...", cls.__name__)
            except KeyError:
                pass
            else:
                yield setup_testcase

    def _cleanup_testcase_methods(self):
        for cls in self.__class__.__mro__:
            try:
                cleanup_testcase = cls.__dict__['cleanup_testcase']
                logger.debug("Running %s.cleanup_testcase()...", cls.__name__)
            except KeyError:
                pass
            else:
                yield cleanup_testcase


    def setup_testcase(self):
        pass

    def cleanup_testcase(self):
        pass


class TestCase(SetupTestCaseMixin, unittest.TestCase):
    def setUp(self):
        try:
            for setup_testcase in self._setup_testcase_methods():
                setup_testcase(self)

        except:
            for cleanup_testcase in self._cleanup_testcase_methods():
                cleanup_testcase(self)

            raise

    def tearDown(self):
        for cleanup_testcase in self._cleanup_testcase_methods():
            cleanup_testcase(self)


class AsyncTestCase(SetupTestCaseMixin, asynctest.TestCase):
    forbid_get_event_loop = True

    async def setUp(self):
        try:
            for setup_testcase in self._setup_testcase_methods():
                c = setup_testcase(self)
                if inspect.isawaitable(c):
                    await c

        except:
            for cleanup_testcase in self._cleanup_testcase_methods():
                c = cleanup_testcase(self)
                if inspect.isawaitable(c):
                    await c

            raise

    async def tearDown(self):
        for cleanup_testcase in self._cleanup_testcase_methods():
            c = cleanup_testcase(self)
            if inspect.isawaitable(c):
                await c


class TestContext(object):
    def __init__(self, *, testcase):
        self.__testcase = testcase

    @property
    def app(self):
        return self.__testcase.app

    @property
    def window(self):
        return self.__testcase.window

    @property
    def event_loop(self):
        return self.__testcase.loop

    @property
    def project_connection(self):
        return self.__testcase.project_connection

    @property
    def project(self):
        return self.__testcase.project

    @property
    def project_client(self):
        return self.__testcase.project_client

    @property
    def selection_set(self):
        return self.__testcase.selection_set

    def call_async(self, coroutine, callback=None):
        task = self.event_loop.create_task(coroutine)
        task.add_done_callback(
            functools.partial(self.__call_async_cb, callback=callback))

    def __call_async_cb(self, task, callback):
        if task.exception() is not None:
            raise task.exception()
        if callback is not None:
            callback(task.result())

    def send_command_async(self, target_id, cmd, callback, **kwargs):
        self.__testcase.commands.append((target_id, cmd, kwargs))
        if callback is not None:
            callback()

    def set_session_value(self, key, value):
        self.__testcase.session_data[key] = value

    def set_session_values(self, data):
        self.__testcase.session_data.update(data)

    def get_session_value(self, key, default):
        return self.__testcase.session_data.get(key, default)

    def add_session_listener(self, key, listener):
        raise NotImplementedError


class QtTestCase(AsyncTestCase):
    use_default_loop = True
    app = None

    @classmethod
    def setUpClass(cls):
        if not constants.TEST_OPTS.ALLOW_UI:
            return

        if cls.app is None:
            cls.app = QtWidgets.QApplication(['unittest'])
            cls.app.setQuitOnLastWindowClosed(False)
        asyncio.set_event_loop(quamash.QEventLoop(cls.app))

    @classmethod
    def tearDownClass(cls):
        asyncio.set_event_loop(None)


class UITestCase(QtTestCase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.context = None

    async def setup_testcase(self):
        self.context = TestContext(testcase=self)
        self.context_args = {'context': self.context}
