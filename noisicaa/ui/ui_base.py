#!/usr/bin/python3

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

import functools
import io
import logging
import traceback

logger = logging.getLogger(__name__)


class CommonContext(object):
    def __init__(self, *, app):
        self.__app = app

    @property
    def app(self):
        return self.__app

    @property
    def window(self):
        return self.__app.win

    @property
    def audioproc_client(self):
        return self.__app.audioproc_client

    @property
    def event_loop(self):
        return self.__app.process.event_loop

    def call_async(self, coroutine, callback=None):
        task = self.event_loop.create_task(coroutine)
        task.add_done_callback(
            functools.partial(self.__call_async_cb, callback=callback))

    def __call_async_cb(self, task, callback):
        if task.exception() is not None:
            buf = io.StringIO()
            task.print_stack(file=buf)

            self.__app.crashWithMessage(
                "Exception in callback",
                buf.getvalue())
            raise exc

        if callback is not None:
            callback(task.result())


class CommonMixin(object):
    def __init__(self, *, context, **kwargs):
        self._context = context
        super().__init__(**kwargs)

    @property
    def context_args(self):
        return {'context': self._context}

    @property
    def app(self):
        return self._context.app

    @property
    def window(self):
        return self._context.window

    @property
    def audioproc_client(self):
        return self._context.audioproc_client

    @property
    def event_loop(self):
        return self._context.event_loop

    def call_async(self, coroutine, callback=None):
        self._context.call_async(coroutine, callback)


class ProjectContext(CommonContext):
    def __init__(self, *, project_connection, selection_set, **kwargs):
        super().__init__(**kwargs)
        self.__project_connection = project_connection
        self.__selection_set = selection_set

    @property
    def selection_set(self):
        return self.__selection_set

    @property
    def project_connection(self):
        return self.__project_connection

    @property
    def project(self):
        return self.__project_connection.client.project

    @property
    def project_client(self):
        return self.__project_connection.client

    def send_command_async(self, target_id, cmd, callback, **kwargs):
        self.call_async(
            self.project_client.send_command(target_id, cmd, **kwargs),
            callback=callback)

    def set_session_value(self, key, value):
        self.project_client.set_session_values({key: value})

    def set_session_values(self, data):
        self.project_client.set_session_values(data)

    def get_session_value(self, key, default):
        return self.project_client.get_session_value(key, default)

    def add_session_listener(self, key, listener):
        return self.project_client.listeners.add('session_data:' + key, listener)


class ProjectMixin(CommonMixin):
    @property
    def selection_set(self):
        return self._context.selection_set

    @property
    def project_connection(self):
        return self._context.project_connection

    @property
    def project(self):
        return self._context.project

    @property
    def project_client(self):
        return self._context.project_client

    def send_command_async(self, target_id, cmd, callback=None, **kwargs):
        self._context.send_command_async(target_id, cmd, callback, **kwargs)

    def set_session_value(self, key, value):
        self._context.set_session_value(key, value)

    def set_session_values(self, data):
        self._context.set_session_values(data)

    def get_session_value(self, key, default):
        return self._context.get_session_value(key, default)

    def add_session_listener(self, key, listener):
        return self._context.add_session_listener(key, listener)
