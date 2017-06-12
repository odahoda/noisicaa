#!/usr/bin/python3

import functools
import io
import logging
import traceback

logger = logging.getLogger(__name__)

UNSET = object()

class CommonMixin(object):
    def __init__(self, *, app=None, **kwargs):
        assert app is not None
        self.__app = app
        super().__init__(**kwargs)

    def _get_context(self):
        return {'app': self.__app}

    @property
    def context(self):
        return self._get_context()

    @property
    def common_context(self):
        return CommonMixin._get_context(self)

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


class ProjectMixin(CommonMixin):
    def __init__(
            self, *, project_connection=None, selection_set=None,
            **kwargs):
        assert project_connection is not None
        self.__project_connection = project_connection
        assert selection_set is not None
        self.__selection_set = selection_set
        super().__init__(**kwargs)

    def _get_context(self):
        context = super()._get_context()
        context['project_connection'] = self.__project_connection
        context['selection_set'] = self.__selection_set
        return context

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

    def send_command_async(self, target_id, cmd, callback=None, **kwargs):
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
