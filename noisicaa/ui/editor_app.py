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
import logging
import os
import sys
import textwrap
import traceback
import types
from typing import Optional, Callable, Sequence, List, Type

from PyQt5.QtCore import Qt
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
from noisicaa import exceptions
from ..constants import EXIT_EXCEPTION, EXIT_RESTART, EXIT_RESTART_CLEAN
from . import clipboard
from . import editor_window
from . import audio_thread_profiler
from . import device_list
from . import project_registry
from . import pipeline_perf_monitor
from . import stat_monitor
from . import settings_dialog
from . import instrument_list
from . import instrument_library
from . import ui_base
from . import open_project_dialog

logger = logging.getLogger('ui.editor_app')


class ExceptHook(object):
    def __init__(self, app: 'EditorApp') -> None:
        self.app = app

    def __call__(
            self, exc_type: Type[BaseException], exc_value: BaseException, tb: types.TracebackType
    ) -> None:
        if issubclass(exc_type, exceptions.RestartAppException):
            self.app.quit(EXIT_RESTART)
            return
        if issubclass(exc_type, exceptions.RestartAppCleanException):
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
    globalMousePosChanged = QtCore.pyqtSignal(QtCore.QPoint)

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

        self.new_project_action = None  # type: QtWidgets.QAction
        self.open_project_action = None  # type: QtWidgets.QAction
        self.restart_action = None  # type: QtWidgets.QAction
        self.restart_clean_action = None  # type: QtWidgets.QAction
        self.crash_action = None  # type: QtWidgets.QAction
        self.about_action = None  # type: QtWidgets.QAction
        self.aboutqt_action = None  # type: QtWidgets.QAction
        self.show_settings_dialog_action = None  # type: QtWidgets.QAction
        self.show_instrument_library_action = None  # type: QtWidgets.QAction
        self.profile_audio_thread_action = None  # type: QtWidgets.QAction
        self.dump_audioproc_action = None  # type: QtWidgets.QAction
        self.show_pipeline_perf_monitor_action = None  # type: QtWidgets.QAction
        self.show_stat_monitor_action = None  # type: QtWidgets.QAction
        self.quit_action = None  # type: QtWidgets.QAction

        self.project_registry = None  # type: project_registry.ProjectRegistry
        self.__audio_thread_profiler = None  # type: audio_thread_profiler.AudioThreadProfiler
        self.audioproc_client = None  # type: audioproc.AbstractAudioProcClient
        self.audioproc_process = None  # type: str
        self.node_db = None  # type: node_db.NodeDBClient
        self.instrument_db = None  # type: instrument_db.InstrumentDBClient
        self.urid_mapper = None  # type: lv2.ProxyURIDMapper
        self.clipboard = None  # type: clipboard.Clipboard
        self.__old_excepthook = None  # type: Callable[[Type[BaseException], BaseException, types.TracebackType], None]
        self.__windows = []  # type: List[editor_window.EditorWindow]
        self.__pipeline_perf_monitor = None  # type: pipeline_perf_monitor.PipelinePerfMonitor
        self.__stat_monitor = None  # type: stat_monitor.StatMonitor
        self.default_style = None  # type: str
        self.instrument_list = None  # type: instrument_list.InstrumentList
        self.devices = None  # type: device_list.DeviceList
        self.setup_complete = None  # type: asyncio.Event
        self.__settings_dialog = None  # type: settings_dialog.SettingsDialog
        self.__instrument_library_dialog = None  # type: instrument_library.InstrumentLibraryDialog

        self.__player_state_listeners = core.CallbackMap[str, audioproc.EngineNotification]()

    @property
    def context(self) -> ui_base.CommonContext:
        return self.__context

    async def setup(self) -> None:
        logger.info("Installing custom excepthook.")
        self.__old_excepthook = sys.excepthook
        sys.excepthook = ExceptHook(self)  # type: ignore[assignment]

        self.setup_complete = asyncio.Event(loop=self.process.event_loop)

        self.default_style = self.qt_app.style().objectName()
        style_name = self.settings.value('appearance/qtStyle', '')
        if style_name:
            # TODO: something's wrong with the QtWidgets stubs...
            self.qt_app.setStyle(QtWidgets.QStyleFactory.create(style_name))  # type: ignore[misc,call-overload]

        self.clipboard = clipboard.Clipboard(qt_app=self.qt_app, context=self.context)
        self.clipboard.setup()

        self.new_project_action = QtWidgets.QAction("New", self.qt_app)
        self.new_project_action.setShortcut(QtGui.QKeySequence.New)
        self.new_project_action.setStatusTip("Create a new project")
        self.new_project_action.setEnabled(False)
        self.new_project_action.triggered.connect(self.__newProject)

        self.open_project_action = QtWidgets.QAction("Open", self.qt_app)
        self.open_project_action.setShortcut(QtGui.QKeySequence.Open)
        self.open_project_action.setStatusTip("Open an existing project")
        self.open_project_action.setEnabled(False)
        self.open_project_action.triggered.connect(self.__openProject)

        self.restart_action = QtWidgets.QAction("Restart", self.qt_app)
        self.restart_action.setShortcut("F5")
        self.restart_action.setShortcutContext(Qt.ApplicationShortcut)
        self.restart_action.setStatusTip("Restart the application")
        self.restart_action.triggered.connect(self.__restart)

        self.restart_clean_action = QtWidgets.QAction("Restart clean", self.qt_app)
        self.restart_clean_action.setShortcut("Ctrl+Shift+F5")
        self.restart_clean_action.setShortcutContext(Qt.ApplicationShortcut)
        self.restart_clean_action.setStatusTip("Restart the application in a clean state")
        self.restart_clean_action.triggered.connect(self.__restartClean)

        self.crash_action = QtWidgets.QAction("Crash", self.qt_app)
        self.crash_action.triggered.connect(self.__crash)

        self.about_action = QtWidgets.QAction("About", self.qt_app)
        self.about_action.setStatusTip("Show the application's About box")
        self.about_action.triggered.connect(self.__about)

        self.aboutqt_action = QtWidgets.QAction("About Qt", self.qt_app)
        self.aboutqt_action.setStatusTip("Show the Qt library's About box")
        self.aboutqt_action.triggered.connect(self.qt_app.aboutQt)

        self.show_settings_dialog_action = QtWidgets.QAction("Settings", self.qt_app)
        self.show_settings_dialog_action.setStatusTip("Open the settings dialog.")
        self.show_settings_dialog_action.setEnabled(False)
        self.show_settings_dialog_action.triggered.connect(self.__showSettingsDialog)

        self.show_instrument_library_action = QtWidgets.QAction("Instrument Library", self.qt_app)
        self.show_instrument_library_action.setStatusTip("Open the instrument library dialog.")
        self.show_instrument_library_action.setEnabled(False)
        self.show_instrument_library_action.triggered.connect(self.__showInstrumentLibrary)

        self.profile_audio_thread_action = QtWidgets.QAction("Profile Audio Thread", self.qt_app)
        self.profile_audio_thread_action.setEnabled(False)
        self.profile_audio_thread_action.triggered.connect(self.__profileAudioThread)

        self.dump_audioproc_action = QtWidgets.QAction("Dump AudioProc", self.qt_app)
        self.dump_audioproc_action.setEnabled(False)
        self.dump_audioproc_action.triggered.connect(self.__dumpAudioProc)

        self.show_pipeline_perf_monitor_action = QtWidgets.QAction(
            "Pipeline Performance Monitor", self.qt_app)
        self.show_pipeline_perf_monitor_action.setEnabled(False)
        self.show_pipeline_perf_monitor_action.setCheckable(True)

        self.show_stat_monitor_action = QtWidgets.QAction("Stat Monitor", self.qt_app)
        self.show_stat_monitor_action.setEnabled(False)
        self.show_stat_monitor_action.setCheckable(True)

        self.quit_action = QtWidgets.QAction("Quit", self.qt_app)
        self.quit_action.setShortcut(QtGui.QKeySequence.Quit)
        self.quit_action.setShortcutContext(Qt.ApplicationShortcut)
        self.quit_action.setStatusTip("Quit the application")
        self.quit_action.triggered.connect(self.quit)

        self.qt_app.installEventFilter(self)

        logger.info("Creating initial window...")
        win = await self.createWindow()
        tab_page = win.addProjectTab()

        progress = win.createSetupProgress()
        try:
            progress.setNumSteps(5)

            logger.info("Creating StatMonitor.")
            self.__stat_monitor = stat_monitor.StatMonitor(context=self.context)
            self.show_stat_monitor_action.setChecked(self.__stat_monitor.isVisible())
            self.show_stat_monitor_action.toggled.connect(
                self.__stat_monitor.setVisible)
            self.__stat_monitor.visibilityChanged.connect(
                self.show_stat_monitor_action.setChecked)

            logger.info("Creating SettingsDialog...")
            self.__settings_dialog = settings_dialog.SettingsDialog(context=self.context)

            with progress.step("Scanning projects..."):
                self.project_registry = project_registry.ProjectRegistry(context=self.context)
                await self.project_registry.setup()

                initial_projects = []
                if self.paths:
                    for path in self.paths:
                        if path.startswith('+'):
                            initial_projects.append((True, path[1:]))
                        else:
                            initial_projects.append((False, path))
                else:
                    for path in self.settings.value('opened_projects', []) or []:
                        initial_projects.append((False, path))

                logger.info(
                    "Starting with projects:\n%s",
                    '\n'.join('%s%s' % ('+' if create else '', path)
                              for create, path in initial_projects))

                idx = 0
                for create, path in initial_projects:
                    if idx == 0:
                        tab = tab_page
                    else:
                        tab = win.addProjectTab()
                    if create:
                        self.process.event_loop.create_task(tab.createProject(path))
                        idx += 1
                    else:
                        try:
                            project = self.project_registry.getProject(path)
                        except KeyError:
                            logging.error("There is no known project at %s", path)
                        else:
                            self.process.event_loop.create_task(tab.openProject(project))
                            idx += 1

                if idx == 0:
                    tab_page.showOpenDialog()

            with progress.step("Scanning nodes and plugins..."):
                await self.createNodeDB()

            with progress.step("Creating URID mapper..."):
                await self.createURIDMapper()

            with progress.step("Setting up audio engine..."):
                self.devices = device_list.DeviceList()
                await self.createAudioProcProcess()

                win.audioprocReady()

                logger.info("Creating AudioThreadProfiler...")
                self.__audio_thread_profiler = audio_thread_profiler.AudioThreadProfiler(
                    context=self.context)

                logger.info("Creating PipelinePerfMonitor...")
                self.__pipeline_perf_monitor = pipeline_perf_monitor.PipelinePerfMonitor(
                    context=self.context)
                self.show_pipeline_perf_monitor_action.setChecked(
                    self.__pipeline_perf_monitor.isVisible())
                self.show_pipeline_perf_monitor_action.toggled.connect(
                    self.__pipeline_perf_monitor.setVisible)
                self.__pipeline_perf_monitor.visibilityChanged.connect(
                    self.show_pipeline_perf_monitor_action.setChecked)

            with progress.step("Scanning instruments..."):
                create_instrument_db_response = editor_main_pb2.CreateProcessResponse()
                await self.process.manager.call(
                    'CREATE_INSTRUMENT_DB_PROCESS', None, create_instrument_db_response)
                instrument_db_address = create_instrument_db_response.address

                self.instrument_db = instrument_db.InstrumentDBClient(
                    self.process.event_loop, self.process.server)
                self.instrument_list = instrument_list.InstrumentList(context=self.context)
                self.instrument_list.setup()
                await self.instrument_db.setup()
                await self.instrument_db.connect(instrument_db_address)

                self.__instrument_library_dialog = instrument_library.InstrumentLibraryDialog(
                    context=self.context)
                await self.__instrument_library_dialog.setup()

        finally:
            win.deleteSetupProgress()

        self.new_project_action.setEnabled(True)
        self.open_project_action.setEnabled(True)
        self.show_settings_dialog_action.setEnabled(True)
        self.show_instrument_library_action.setEnabled(True)
        self.profile_audio_thread_action.setEnabled(True)
        self.dump_audioproc_action.setEnabled(True)
        self.show_pipeline_perf_monitor_action.setEnabled(True)
        self.show_stat_monitor_action.setEnabled(True)
        self.setup_complete.set()

    async def cleanup(self) -> None:
        logger.info("Cleanup app...")

        self.qt_app.removeEventFilter(self)

        if self.__stat_monitor is not None:
            self.__stat_monitor.storeState()
            self.__stat_monitor = None

        if self.__pipeline_perf_monitor is not None:
            self.__pipeline_perf_monitor.storeState()
            self.__pipeline_perf_monitor = None

        if self.__audio_thread_profiler is not None:
            self.__audio_thread_profiler.hide()
            self.__audio_thread_profiler = None

        if self.__instrument_library_dialog is not None:
            await self.__instrument_library_dialog.cleanup()
            self.__instrument_library_dialog = None

        if self.__settings_dialog is not None:
            self.__settings_dialog.storeState()
            self.__settings_dialog.close()
            self.__settings_dialog = None

        while self.__windows:
            win = self.__windows.pop(0)
            win.storeState()
            await win.cleanup()

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

        if self.instrument_list is not None:
            self.instrument_list.cleanup()
            self.instrument_list = None

        if self.instrument_db is not None:
            await self.instrument_db.disconnect()
            await self.instrument_db.cleanup()
            self.instrument_db = None

        if self.node_db is not None:
            await self.node_db.disconnect()
            await self.node_db.cleanup()
            self.node_db = None

        if self.clipboard is not None:
            self.clipboard.cleanup()
            self.clipboard = None

        self.settings.sync()
        self.dumpSettings()

        logger.info("Remove custom excepthook.")
        sys.excepthook = self.__old_excepthook  # type: ignore[assignment]

    def eventFilter(self, target: QtCore.QObject, evt: QtCore.QEvent) -> bool:
        if evt.type() == QtCore.QEvent.MouseMove:
            assert isinstance(evt, QtGui.QMouseEvent), evt
            assert isinstance(target, (QtWidgets.QWidget, QtGui.QWindow)), target
            self.globalMousePosChanged.emit(target.mapToGlobal(evt.pos()))
        return super().eventFilter(target, evt)

    async def createWindow(self) -> editor_window.EditorWindow:
        win = editor_window.EditorWindow(context=self.context)
        await win.setup()
        self.__windows.append(win)
        return win

    async def deleteWindow(self, win: editor_window.EditorWindow) -> None:
        self.__windows.remove(win)
        await win.cleanup()

        if not self.__windows:
            self.quit()

    def windows(self) -> List[editor_window.EditorWindow]:
        return self.__windows

    def quit(self, exit_code: int = 0) -> None:
        # TODO: quit() is not a method of ProcessBase, only in UIProcess. Find some way to
        #   fix that without a cyclic import.
        self.process.quit(exit_code)  # type: ignore[attr-defined]

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

    def __handleEngineNotification(self, msg: audioproc.EngineNotification) -> None:
        for device_manager_message in msg.device_manager_messages:
            action = device_manager_message.WhichOneof('action')
            if action == 'added':
                self.devices.addDevice(device_manager_message.added)
            elif action == 'removed':
                self.devices.removeDevice(device_manager_message.removed)
            else:
                raise ValueError(action)

    def __newProject(self) -> None:
        win = self.__windows[0]
        dialog = open_project_dialog.NewProjectDialog(parent=win, context=self.context)
        dialog.setModal(True)
        dialog.finished.connect(functools.partial(self.__newProjectDialogDone, dialog, win))
        dialog.show()

    def __newProjectDialogDone(
            self,
            dialog: open_project_dialog.NewProjectDialog,
            win: editor_window.EditorWindow,
            result: int
    ) -> None:
        if result != QtWidgets.QDialog.Accepted:
            return

        path = dialog.projectPath()
        tab = win.addProjectTab()
        self.process.event_loop.create_task(tab.createProject(path))

    def __openProject(self) -> None:
        win = self.__windows[0]
        tab = win.addProjectTab()
        tab.showOpenDialog()

    def __about(self) -> None:
        QtWidgets.QMessageBox.about(
            None, "About noisicaä",
            textwrap.dedent("""\
                Some text goes here...
                """))

    def __restart(self) -> None:
        raise exceptions.RestartAppException("Restart requested by user.")

    def __restartClean(self) -> None:
        raise exceptions.RestartAppCleanException("Clean restart requested by user.")

    def __crash(self) -> None:
        raise RuntimeError("Something bad happened")

    def __showInstrumentLibrary(self) -> None:
        self.__instrument_library_dialog.show()
        self.__instrument_library_dialog.activateWindow()

    def __showSettingsDialog(self) -> None:
        self.__settings_dialog.show()
        self.__settings_dialog.activateWindow()

    def __profileAudioThread(self) -> None:
        self.__audio_thread_profiler.show()
        self.__audio_thread_profiler.raise_()
        self.__audio_thread_profiler.activateWindow()

    def __dumpAudioProc(self) -> None:
        self.process.event_loop.create_task(self.audioproc_client.dump())

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
