#!/usr/bin/python3

import functools

UNSET = object()

class CommonMixin(object):
    def __init__(self, __no_positional_args=UNSET, app=None, **kwargs):
        assert __no_positional_args is UNSET
        assert app is not None
        self.__app = app
        super().__init__(**kwargs)

    def _get_context(self):
        return {'app': self.__app}

    @property
    def context(self):
        return self._get_context()

    @property
    def app(self):
        return self.__app

    @property
    def window(self):
        return self.__app.win

    @property
    def event_loop(self):
        return self.__app.process.event_loop

    def call_async(self, coroutine, callback=None):
        task = self.event_loop.create_task(coroutine)
        task.add_done_callback(
            functools.partial(self.__call_async_cb, callback=callback))

    def __call_async_cb(self, task, callback):
        if task.exception() is not None:
            raise task.exception()
        if callback is not None:
            callback(task.result())

class ProjectMixin(CommonMixin):
    def __init__(
            self, __no_positional_args=UNSET, project_connection=None,
            **kwargs):
        assert __no_positional_args is UNSET
        assert project_connection is not None
        self.__project_connection = project_connection
        super().__init__(**kwargs)

    def _get_context(self):
        context = super()._get_context()
        context['project_connection'] = self.__project_connection
        return context

    @property
    def project_connection(self):
        return self.__project_connection

    @property
    def project(self):
        return self.__project_connection.client.project

    @property
    def project_client(self):
        return self.__project_connection.client

