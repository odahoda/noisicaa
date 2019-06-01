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
import logging
import os
import pprint
import sys
import traceback
import types
from typing import Any, Optional, Callable, Sequence, List, Type

from PyQt5 import QtCore
from PyQt5 import QtGui
from PyQt5 import QtWidgets

from noisicaa import audioproc
from noisicaa import instrument_db
from noisicaa import node_db
from noisicaa import core
from noisicaa import lv2
from noisicaa import editor_main_pb2
from noisicaa import runtime_settings as runtime_settings_lib
from ..exceptions import RestartAppException, RestartAppCleanException
from ..constants import EXIT_EXCEPTION, EXIT_RESTART, EXIT_RESTART_CLEAN
from . import editor_window
from . import audio_thread_profiler
from . import device_list
from . import project_registry
from . import pipeline_perf_monitor
from . import stat_monitor
from . import ui_base

logger = logging.getLogger('ui.editor_app')


class ExceptHook(object):
    def __init__(self, app: 'EditorApp') -> None:
        self.app = app

    def __call__(
            self, exc_type: Type[BaseException], exc_value: BaseException, tb: types.TracebackType
    ) -> None:
        if issubclass(exc_type, RestartAppException):
            self.app.quit(EXIT_RESTART)
            return
        if issubclass(exc_type, RestartAppCleanException):
            self.app.quit(EXIT_RESTART_CLEAN)
            return

        msg = ''.join(traceback.format_exception(exc_type, exc_value, tb))

        logger.error("Uncaught exception:\n%s", msg)
        self.app.crashWithMessage("Uncaught exception", msg)


class QApplication(QtWidgets.QApplication):
    def __init__(self) -> None:
        super().__init__(['noisicaä'])

        self.setQuitOnLastWindowClosed(False)


class EditorApp(ui_base.AbstractEditorApp):
    def __init__(
            self, *,
            qt_app: QtWidgets.QApplication,
            process: core.ProcessBase,
            paths: Sequence[str],
            runtime_settings: runtime_settings_lib.RuntimeSettings,
            settings: Optional[QtCore.QSettings] = None
    ) -> None:
        self.__context = ui_base.CommonContext(app=self)

        super().__init__()

        self.paths = paths
        self.qt_app = qt_app
        self.process = process
        self.runtime_settings = runtime_settings

        if settings is None:
            settings = QtCore.QSettings('odahoda.de', 'noisicaä')
            if runtime_settings.start_clean:
                settings.clear()
        self.settings = settings
        self.dumpSettings()

        self.project_registry = None  # type: project_registry.ProjectRegistry
        self.__audio_thread_profiler = None  # type: audio_thread_profiler.AudioThreadProfiler
        self.profile_audio_thread_action = None  # type: QtWidgets.QAction
        self.dump_audioproc = None  # type: QtWidgets.QAction
        self.audioproc_client = None  # type: audioproc.AbstractAudioProcClient
        self.audioproc_process = None  # type: str
        self.node_db = None  # type: node_db.NodeDBClient
        self.instrument_db = None  # type: instrument_db.InstrumentDBClient
        self.urid_mapper = None  # type: lv2.ProxyURIDMapper
        self.__clipboard = None  # type: Any
        self.__old_excepthook = None  # type: Callable[[Type[BaseException], BaseException, types.TracebackType], None]
        self.__windows = []  # type: List[editor_window.EditorWindow]
        self.pipeline_perf_monitor = None  # type: pipeline_perf_monitor.PipelinePerfMonitor
        self.stat_monitor = None  # type: stat_monitor.StatMonitor
        self.default_style = None  # type: str
        self.devices = None  # type: device_list.DeviceList
        self.setup_complete = None  # type: asyncio.Event
        self.__player_state_listeners = core.CallbackMap[str, audioproc.EngineNotification]()

    @property
    def context(self) -> ui_base.CommonContext:
        return self.__context

    async def setup(self) -> None:
        logger.info("Installing custom excepthook.")
        self.__old_excepthook = sys.excepthook
        sys.excepthook = ExceptHook(self)  # type: ignore

        self.setup_complete = asyncio.Event(loop=self.process.event_loop)
        self.default_style = self.qt_app.style().objectName()

        style_name = self.settings.value('appearance/qtStyle', '')
        if style_name:
            # TODO: something's wrong with the QtWidgets stubs...
            self.qt_app.setStyle(QtWidgets.QStyleFactory.create(style_name))  # type: ignore

        logger.info("Creating initial window...")
        win = await self.createWindow()
        tab_page = win.addProjectTab("Open project")

        progress = win.createSetupProgress()
        try:
            progress.setNumSteps(4)

            with progress.step("Scanning projects..."):
                self.project_registry = project_registry.ProjectRegistry(self.process.event_loop)
                await self.project_registry.setup()
                tab_page.showOpenDialog(self.project_registry)

            with progress.step("Scanning nodes and plugins..."):
                await self.createNodeDB()

            with progress.step("Scanning instruments..."):
                await self.createInstrumentDB()

            with progress.step("Creating URID mapper..."):
                await self.createURIDMapper()

            with progress.step("Setting up audio engine..."):
                self.devices = device_list.DeviceList()
                await self.createAudioProcProcess()

        finally:
            win.deleteSetupProgress()

        self.setup_complete.set()

        # self.__audio_thread_profiler = audio_thread_profiler.AudioThreadProfiler(
        #     context=self.context)
        # self.profile_audio_thread_action = QtWidgets.QAction("Profile Audio Thread", self.qt_app)
        # self.profile_audio_thread_action.triggered.connect(self.onProfileAudioThread)

        # self.dump_audioproc = QtWidgets.QAction("Dump AudioProc", self.qt_app)
        # self.dump_audioproc.triggered.connect(self.onDumpAudioProc)


        # logger.info("Creating PipelinePerfMonitor.")
        # self.pipeline_perf_monitor = pipeline_perf_monitor.PipelinePerfMonitor(context=self.context)

        # logger.info("Creating StatMonitor.")
        # self.stat_monitor = stat_monitor.StatMonitor(context=self.context)

        # if self.paths:
        #     logger.info("Starting with projects from cmdline.")
        #     for path in self.paths:
        #         if path.startswith('+'):
        #             await self.createProject(path[1:])
        #         else:
        #             await self.openProject(path)
        # else:
        #     reopen_projects = self.settings.value('opened_projects', [])
        #     for path in reopen_projects or []:
        #         await self.openProject(path)

    async def cleanup(self) -> None:
        logger.info("Cleanup app...")

        # if self.stat_monitor is not None:
        #     self.stat_monitor.storeState()
        #     self.stat_monitor = None

        # if self.pipeline_perf_monitor is not None:
        #     self.pipeline_perf_monitor.storeState()
        #     self.pipeline_perf_monitor = None

        # if self.__audio_thread_profiler is not None:
        #     self.__audio_thread_profiler.hide()
        #     self.__audio_thread_profiler = None

        while self.__windows:
            win = self.__windows.pop(0)
            win.storeState()
            await win.cleanup()

        # self.settings.sync()
        # self.dumpSettings()

        if self.project_registry is not None:
            await self.project_registry.cleanup()
            self.project_registry = None

        if self.audioproc_client is not None:
            await self.audioproc_client.disconnect()
            await self.audioproc_client.cleanup()
            self.audioproc_client = None

        if self.audioproc_process is not None:
            await self.process.manager.call(
                'SHUTDOWN_PROCESS',
                editor_main_pb2.ShutdownProcessRequest(
                    address=self.audioproc_process))
            self.audioproc_process = None

        if self.urid_mapper is not None:
            await self.urid_mapper.cleanup(self.process.event_loop)
            self.urid_mapper = None

        if self.instrument_db is not None:
            await self.instrument_db.disconnect()
            await self.instrument_db.cleanup()
            self.instrument_db = None

        if self.node_db is not None:
            await self.node_db.disconnect()
            await self.node_db.cleanup()
            self.node_db = None

        logger.info("Remove custom excepthook.")
        sys.excepthook = self.__old_excepthook  # type: ignore

    async def createWindow(self) -> editor_window.EditorWindow:
        win = editor_window.EditorWindow(context=self.context)
        await win.setup()
        win.show()
        self.__windows.append(win)
        return win

    def quit(self, exit_code: int = 0) -> None:
        # TODO: quit() is not a method of ProcessBase, only in UIProcess. Find some way to
        #   fix that without a cyclic import.
        self.process.quit(exit_code)  # type: ignore

    async def createAudioProcProcess(self) -> None:
        create_audioproc_request = editor_main_pb2.CreateAudioProcProcessRequest(
            name='main',
            host_parameters=audioproc.HostParameters(
                block_size=2 ** int(self.settings.value('audio/block_size', 10)),
                sample_rate=int(self.settings.value('audio/sample_rate', 44100))))
        create_audioproc_response = editor_main_pb2.CreateProcessResponse()
        await self.process.manager.call(
            'CREATE_AUDIOPROC_PROCESS', create_audioproc_request, create_audioproc_response)
        self.audioproc_process = create_audioproc_response.address

        self.audioproc_client = audioproc.AudioProcClient(
            self.process.event_loop, self.process.server, self.urid_mapper)
        self.audioproc_client.engine_notifications.add(self.__handleEngineNotification)
        await self.audioproc_client.setup()
        await self.audioproc_client.connect(
            self.audioproc_process, {'perf_data'})

        await self.audioproc_client.create_realm(name='root')

        await self.audioproc_client.set_backend(
            self.settings.value('audio/backend', 'portaudio'),
        )

    async def createNodeDB(self) -> None:
        create_node_db_response = editor_main_pb2.CreateProcessResponse()
        await self.process.manager.call(
            'CREATE_NODE_DB_PROCESS', None, create_node_db_response)
        node_db_address = create_node_db_response.address

        self.node_db = node_db.NodeDBClient(self.process.event_loop, self.process.server)
        await self.node_db.setup()
        await self.node_db.connect(node_db_address)

    async def createInstrumentDB(self) -> None:
        create_instrument_db_response = editor_main_pb2.CreateProcessResponse()
        await self.process.manager.call(
            'CREATE_INSTRUMENT_DB_PROCESS', None, create_instrument_db_response)
        instrument_db_address = create_instrument_db_response.address

        self.instrument_db = instrument_db.InstrumentDBClient(
            self.process.event_loop, self.process.server)
        await self.instrument_db.setup()
        await self.instrument_db.connect(instrument_db_address)

    async def createURIDMapper(self) -> None:
        create_urid_mapper_response = editor_main_pb2.CreateProcessResponse()
        await self.process.manager.call(
            'CREATE_URID_MAPPER_PROCESS', None, create_urid_mapper_response)
        urid_mapper_address = create_urid_mapper_response.address

        self.urid_mapper = lv2.ProxyURIDMapper(
            server_address=urid_mapper_address,
            tmp_dir=self.process.tmp_dir)
        await self.urid_mapper.setup(self.process.event_loop)

    def dumpSettings(self) -> None:
        for key in self.settings.allKeys():
            value = self.settings.value(key)
            if isinstance(value, (bytes, QtCore.QByteArray)):
                value = '[%d bytes]' % len(value)
            logger.info('%s: %s', key, value)

    def onProfileAudioThread(self) -> None:
        self.__audio_thread_profiler.show()
        self.__audio_thread_profiler.raise_()
        self.__audio_thread_profiler.activateWindow()

    def onDumpAudioProc(self) -> None:
        self.process.event_loop.create_task(self.audioproc_client.dump())

    def __handleEngineNotification(self, msg: audioproc.EngineNotification) -> None:
        for device_manager_message in msg.device_manager_messages:
            action = device_manager_message.WhichOneof('action')
            if action == 'added':
                self.devices.addDevice(device_manager_message.added)
            elif action == 'removed':
                self.devices.removeDevice(device_manager_message.removed)
            else:
                raise ValueError(action)

    # pylint: disable=line-too-long
    # def onPlayerStatus(self, player_state: audioproc.PlayerState):
    #     if pipeline_disabled:
    #         dialog = QtWidgets.QMessageBox(self)
    #         dialog.setIcon(QtWidgets.QMessageBox.Critical)
    #         dialog.setWindowTitle("noisicaa - Crash")
    #         dialog.setText(
    #             "The audio pipeline has been disabled, because it is repeatedly crashing.")
    #         quit_button = dialog.addButton("Quit", QtWidgets.QMessageBox.DestructiveRole)
    #         undo_and_restart_button = dialog.addButton(
    #             "Undo last command and restart pipeline", QtWidgets.QMessageBox.ActionRole)
    #         restart_button = dialog.addButton("Restart pipeline", QtWidgets.QMessageBox.AcceptRole)
    #         dialog.setDefaultButton(restart_button)
    #         dialog.finished.connect(lambda _: self.call_async(
    #             self.onPipelineDisabledDialogFinished(
    #                 dialog, quit_button, undo_and_restart_button, restart_button)))
    #         dialog.show()

    # async def onPipelineDisabledDialogFinished(
    #         self, dialog: QtWidgets.QMessageBox, quit_button: QtWidgets.QAbstractButton,
    #         undo_and_restart_button: QtWidgets.QAbstractButton,
    #         restart_button: QtWidgets.QAbstractButton) -> None:
    #     if dialog.clickedButton() == quit_button:
    #         self.app.quit()

    #     elif dialog.clickedButton() == restart_button:
    #         await self.project_client.restart_player_pipeline(self.__player_id)

    #     elif dialog.clickedButton() == undo_and_restart_button:
    #         await self.project_client.undo()
    #         await self.project_client.restart_player_pipeline(self.__player_id)
    # pylint: enable=line-too-long

    def setClipboardContent(self, content: Any) -> None:
        logger.info(
            "Setting clipboard contents to: %s", pprint.pformat(content))
        self.__clipboard = content

    def clipboardContent(self) -> Any:
        return self.__clipboard

    # async def createProject(self, path: str) -> None:
    #     project_connection = self.project_registry.add_project(path)
    #     idx = self.win.addProjectSetupView(project_connection)
    #     await project_connection.create()
    #     await self.win.activateProjectView(idx, project_connection)
    #     self._updateOpenedProjects()

    # async def openProject(self, path: str) -> None:
    #     project_connection = self.project_registry.add_project(path)
    #     idx = self.win.addProjectSetupView(project_connection)
    #     await project_connection.open()
    #     await self.win.activateProjectView(idx, project_connection)
    #     self._updateOpenedProjects()

    # def _updateOpenedProjects(self) -> None:
    #     self.settings.setValue(
    #         'opened_projects',
    #         sorted(
    #             project.path
    #             for project in self.project_registry.projects.values()
    #             if project.path))

    # async def removeProject(self, project_connection: project_registry.Project) -> None:
    #     await self.win.removeProjectView(project_connection)
    #     await self.project_registry.close_project(project_connection)
    #     self._updateOpenedProjects()

    def crashWithMessage(self, title: str, msg: str) -> None:
        logger.error('%s: %s', title, msg)

        try:
            errorbox = QtWidgets.QMessageBox()
            errorbox.setWindowTitle("noisicaä crashed")
            errorbox.setText(title)
            errorbox.setInformativeText(msg)
            errorbox.setIcon(QtWidgets.QMessageBox.Critical)
            errorbox.addButton("Exit", QtWidgets.QMessageBox.AcceptRole)
            errorbox.exec_()
        except:  # pylint: disable=bare-except
            logger.error(
                "Failed to show crash dialog: %s", traceback.format_exc())

        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(EXIT_EXCEPTION)
