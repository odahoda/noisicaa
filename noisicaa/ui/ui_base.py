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
import io
import typing
from typing import Any, Optional, Dict, Tuple, Callable, Awaitable

from PyQt5 import QtCore
from PyQt5 import QtWidgets

from noisicaa import audioproc
from noisicaa import music
from noisicaa import core
from . import selection_set as selection_set_lib
from . import project_registry

if typing.TYPE_CHECKING:
    from . import device_list
    from noisicaa import instrument_db as instrument_db_lib
    from noisicaa import node_db as node_db_lib
    from noisicaa import runtime_settings as runtime_settings_lib
    from noisicaa import lv2


class CommonContext(object):
    def __init__(self, *, app: 'AbstractEditorApp') -> None:
        self.__app = app

    @property
    def qt_app(self) -> QtWidgets.QApplication:
        return self.__app.qt_app

    @property
    def app(self) -> 'AbstractEditorApp':
        return self.__app

    @property
    def editor_window(self) -> 'AbstractEditorWindow':
        return self.__app.win

    @property
    def audioproc_client(self) -> audioproc.AbstractAudioProcClient:
        return self.__app.audioproc_client

    @property
    def event_loop(self) -> asyncio.AbstractEventLoop:
        return self.__app.process.event_loop

    def call_async(
            self, coroutine: Awaitable, callback: Optional[Callable[[Any], None]] = None
    ) -> asyncio.Task:
        task = self.event_loop.create_task(coroutine)
        task.add_done_callback(
            functools.partial(self.__call_async_cb, callback=callback))
        return task

    def __call_async_cb(
            self, task: asyncio.Task, callback: Optional[Callable[[Any], None]]) -> None:
        if task.exception() is not None:
            buf = io.StringIO()
            task.print_stack(file=buf)

            self.__app.crashWithMessage(
                "Exception in callback",
                buf.getvalue())
            raise task.exception()

        if callback is not None:
            callback(task.result())


class CommonMixin(object):
    def __init__(self, *, context: CommonContext, **kwargs: Any) -> None:
        self._context = context

        # This is a mixin class, so actual super class is not object.
        super().__init__(**kwargs)  # type: ignore

    @property
    def context(self) -> CommonContext:
        return self._context

    @property
    def qt_app(self) -> QtWidgets.QApplication:
        return self._context.qt_app

    @property
    def app(self) -> 'AbstractEditorApp':
        return self._context.app

    @property
    def editor_window(self) -> 'AbstractEditorWindow':
        return self._context.editor_window

    @property
    def audioproc_client(self) -> audioproc.AbstractAudioProcClient:
        return self._context.audioproc_client

    @property
    def event_loop(self) -> asyncio.AbstractEventLoop:
        return self._context.event_loop

    def call_async(
            self, coroutine: Awaitable, callback: Optional[Callable[[Any], None]] = None
    ) -> asyncio.Task:
        return self._context.call_async(coroutine, callback)


class ProjectContext(CommonContext):
    def __init__(
            self, *,
            project_connection: project_registry.Project,
            selection_set: selection_set_lib.SelectionSet,
            project_view: 'AbstractProjectView',
            **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.__project_connection = project_connection
        self.__selection_set = selection_set
        self.__project_view = project_view

    @property
    def selection_set(self) -> selection_set_lib.SelectionSet:
        return self.__selection_set

    @property
    def project_view(self) -> 'AbstractProjectView':
        return self.__project_view

    @property
    def project_connection(self) -> project_registry.Project:
        return self.__project_connection

    @property
    def project(self) -> music.Project:
        return self.__project_connection.client.project

    @property
    def project_client(self) -> music.ProjectClient:
        return self.__project_connection.client

    def send_command_async(self, cmd: music.Command) -> asyncio.Task:
        return self.call_async(self.project_client.send_command(cmd))

    def send_commands_async(self, *cmd: music.Command) -> asyncio.Task:
        return self.call_async(self.project_client.send_commands(*cmd))

    def set_session_value(self, key: str, value: Any) -> None:
        self.project_client.set_session_values({key: value})

    def set_session_values(self, data: Dict[str, Any]) -> None:
        self.project_client.set_session_values(data)

    def get_session_value(self, key: str, default: Any) -> Any:
        return self.project_client.get_session_value(key, default)

    def add_session_listener(self, key: str, listener: Callable[[Any], None]) -> core.Listener:
        return self.project_client.add_session_data_listener(key, listener)


class ProjectMixin(CommonMixin):
    _context = None  # type: ProjectContext

    @property
    def selection_set(self) -> selection_set_lib.SelectionSet:
        return self._context.selection_set

    @property
    def project_connection(self) -> project_registry.Project:
        return self._context.project_connection

    @property
    def project(self) -> music.Project:
        return self._context.project

    @property
    def project_view(self) -> 'AbstractProjectView':
        return self._context.project_view

    @property
    def time_mapper(self) -> audioproc.TimeMapper:
        return self._context.project.time_mapper

    @property
    def project_client(self) -> music.ProjectClient:
        return self._context.project_client

    def send_command_async(self, command: music.Command) -> asyncio.Task:
        return self._context.send_command_async(command)

    def send_commands_async(self, *commands: music.Command) -> asyncio.Task:
        return self._context.send_commands_async(*commands)

    def set_session_value(self, key: str, value: Any) -> None:
        self._context.set_session_value(key, value)

    def set_session_values(self, data: Dict[str, Any]) -> None:
        self._context.set_session_values(data)

    def get_session_value(self, key: str, default: Any) -> Any:
        return self._context.get_session_value(key, default)

    def add_session_listener(self, key: str, listener: Callable[[Any], None]) -> core.Listener:
        return self._context.add_session_listener(key, listener)


class AbstractProjectView(ProjectMixin):
    async def createPluginUI(self, node_id: str) -> Tuple[int, Tuple[int, int]]:
        raise NotImplementedError

    async def deletePluginUI(self, node_id: str) -> None:
        raise NotImplementedError

    async def sendNodeMessage(self, msg: audioproc.ProcessorMessage) -> None:
        raise NotImplementedError


class AbstractEditorWindow(CommonMixin, QtWidgets.QMainWindow):
    pipeline_status = None  # type: QtWidgets.QLabel


class AbstractPipelinePerfMonitor(CommonMixin, QtWidgets.QMainWindow):
    visibilityChanged = None  # type: QtCore.pyqtSignal


class AbstractStatMonitor(CommonMixin, QtWidgets.QMainWindow):
    visibilityChanged = None  # type: QtCore.pyqtSignal


class AbstractEditorApp(object):
    win = None  # type: AbstractEditorWindow
    audioproc_client = None  # type: audioproc.AbstractAudioProcClient
    process = None  # type: core.ProcessBase
    settings = None  # type: QtCore.QSettings
    pipeline_perf_monitor = None  # type: AbstractPipelinePerfMonitor
    stat_monitor = None  # type: AbstractStatMonitor
    runtime_settings = None  # type: runtime_settings_lib.RuntimeSettings
    show_edit_areas_action = None  # type: QtWidgets.QAction
    profile_audio_thread_action = None  # type: QtWidgets.QAction
    dump_audioproc = None  # type: QtWidgets.QAction
    node_db = None  # type: node_db_lib.NodeDBClient
    instrument_db = None  # type: instrument_db_lib.InstrumentDBClient
    urid_mapper = None  # type: lv2.ProxyURIDMapper
    default_style = None  # type: str
    qt_app = None  # type: QtWidgets.QApplication
    devices = None  # type: device_list.DeviceList

    def quit(self, exit_code: int = 0) -> None:
        raise NotImplementedError

    async def createProject(self, path: str) -> None:
        raise NotImplementedError

    async def openProject(self, path: str) -> None:
        raise NotImplementedError

    async def removeProject(self, project_connection: project_registry.Project) -> None:
        raise NotImplementedError

    def crashWithMessage(self, title: str, msg: str) -> None:
        raise NotImplementedError

    def setClipboardContent(self, content: Any) -> None:
        raise NotImplementedError

    def clipboardContent(self) -> Any:
        raise NotImplementedError
