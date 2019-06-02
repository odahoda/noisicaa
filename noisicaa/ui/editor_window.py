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
import contextlib
import logging
import textwrap
import time
import typing
from typing import cast, Any, Optional, Iterator, Callable

from PyQt5.QtCore import Qt
from PyQt5 import QtCore
from PyQt5 import QtGui
from PyQt5 import QtWidgets

from noisicaa import constants
from noisicaa import audioproc
from noisicaa import music
from ..exceptions import RestartAppException, RestartAppCleanException
from . import project_view
from . import ui_base
from . import qprogressindicator
from . import project_registry as project_registry_lib
from . import load_history
from . import slots
from . import open_project_dialog

if typing.TYPE_CHECKING:
    from noisicaa import core

logger = logging.getLogger(__name__)


class SetupProgressWidget(QtWidgets.QWidget):
    def __init__(self, parent: QtWidgets.QWidget) -> None:
        super().__init__(parent)

        self.__step = 0
        self.__num_steps = 1

        self.__message = QtWidgets.QLabel(self)
        message_font = QtGui.QFont(self.__message.font())
        message_font.setBold(True)
        self.__message.setFont(message_font)
        self.__message.setText("Initializing noisicaä...")
        self.__bar = QtWidgets.QProgressBar(self)

        layout = QtWidgets.QVBoxLayout()
        layout.setContentsMargins(8, 4, 8, 4)
        layout.addWidget(self.__message)
        layout.addWidget(self.__bar)
        self.setLayout(layout)

    def setNumSteps(self, num_steps: int) -> None:
        self.__num_steps = num_steps
        self.__bar.setRange(0, num_steps)

    @contextlib.contextmanager
    def step(self, message: str) -> None:
        self.__step += 1
        self.__bar.setValue(self.__step)
        self.__message.setText("Initializing noisicaä: %s" % message)
        yield
        if self.__step == self.__num_steps:
            self.__message.setText("Initialization complete.")


class ProjectTabPage(ui_base.CommonMixin, QtWidgets.QWidget):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.__page = None  # type: QtWidgets.QWidget
        self.__page_cleanup_func = None  # type: Callable[[], None]

        self.__layout = QtWidgets.QVBoxLayout()
        self.__layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(self.__layout)

    def __setPage(self, page: QtWidgets.QWidget, cleanup_func: Callable[[], None] = None) -> None:
        if self.__page is not None:
            self.__layout.removeWidget(self.__page)
            self.__page.setParent(None)
            self.__page = None
            if self.__page_cleanup_func is not None:
                self.__page_cleanup_func()
                self.__page_cleanup_func = None

        self.__layout.addWidget(page)
        self.__page = page
        self.__page_cleanup_func = cleanup_func

    def showOpenDialog(self, project_registry: project_registry_lib.ProjectRegistry) -> None:
        dialog = open_project_dialog.OpenProjectDialog(self, project_registry=project_registry)
        dialog.projectSelected.connect(lambda project: self.call_async(self.__projectSelected(project)))

        l1 = QtWidgets.QVBoxLayout()
        l1.addSpacing(32)
        l1.addWidget(dialog, 6)
        l1.addStretch(1)

        l2 = QtWidgets.QHBoxLayout()
        l2.addStretch(1)
        l2.addLayout(l1, 3)
        l2.addStretch(1)

        page = QtWidgets.QWidget(self)
        page.setLayout(l2)

        self.__setPage(page, dialog.cleanup)

    async def __projectSelected(self, project: project_registry_lib.Project) -> None:
        self.showLoadSpinner("Loading project \"%s\"..." % project.name)
        await self.app.setup_complete.wait()
        await project.open()
        view = project_view.ProjectView(project_connection=project, context=self.context)
        await view.setup()
        self.__setPage(view)

    def showLoadSpinner(self, message: str) -> None:
        page = QtWidgets.QWidget(self)

        label = QtWidgets.QLabel(page)
        label.setText(message)

        wheel = qprogressindicator.QProgressIndicator(page)
        wheel.setMinimumSize(48, 48)
        wheel.setMaximumSize(48, 48)
        wheel.setAnimationDelay(100)
        wheel.startAnimation()

        layout = QtWidgets.QVBoxLayout()
        layout.addStretch(2)
        layout.addWidget(label, 0, Qt.AlignHCenter)
        layout.addSpacing(10)
        layout.addWidget(wheel, 0, Qt.AlignHCenter)
        layout.addStretch(3)
        page.setLayout(layout)

        self.__setPage(page)


class EditorWindow(ui_base.AbstractEditorWindow):
    # Could not figure out how to define a signal that takes either an instance
    # of a specific class or None.
    # currentProjectChanged = QtCore.pyqtSignal(object)
    # currentTrackChanged = QtCore.pyqtSignal(object)
    # playingChanged = QtCore.pyqtSignal(bool)
    # loopEnabledChanged = QtCore.pyqtSignal(bool)

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

    #     self.__engine_state_listener = None  # type: core.Listener[audioproc.EngineStateChange]

    #     self._current_project_view = None  # type: Optional[ProjectView]

        self.setWindowTitle("noisicaä")
        self.resize(1200, 800)

        self.__setup_progress = None  # type: SetupProgressWidget
        self.__setup_progress_fade_task = None  # type: asyncio.Task

    #     self.createActions()
        self.createMenus()
    #     self.createToolBar()
    #     self.createStatusBar()

    #     self.playingChanged.connect(self.onPlayingChanged)
    #     self.loopEnabledChanged.connect(self.onLoopEnabledChanged)

        self.__project_tabs = QtWidgets.QTabWidget(self)
        self.__project_tabs.setTabBarAutoHide(True)
        self.__project_tabs.setUsesScrollButtons(True)
        self.__project_tabs.setTabsClosable(True)
        self.__project_tabs.setMovable(True)
        self.__project_tabs.setDocumentMode(True)

        #self.__project_tabs.tabCloseRequested.connect(self.onCloseProjectTab)
        #self.__project_tabs.currentChanged.connect(self.onCurrentProjectTabChanged)

    #     self._start_view = self.createStartView()

    #     self._main_area = QtWidgets.QStackedWidget(self)
    #     self._main_area.addWidget(self._project_tabs)
    #     self._main_area.addWidget(self._start_view)
    #     self._main_area.setCurrentIndex(1)
    #     self.setCentralWidget(self._main_area)

        self.__main_layout = QtWidgets.QVBoxLayout()
        self.__main_layout.setContentsMargins(0, 0, 0, 0)
        self.__main_layout.addWidget(self.__project_tabs)

        self.__main_area = QtWidgets.QWidget()
        self.__main_area.setLayout(self.__main_layout)
        self.setCentralWidget(self.__main_area)

        self.restoreGeometry(
            self.app.settings.value('mainwindow/geometry', b''))
        self.restoreState(
            self.app.settings.value('mainwindow/state', b''))

    async def setup(self) -> None:
        # self.__engine_state_listener = self.audioproc_client.engine_state_changed.add(
        #     self.__engineStateChanged)

        pass

    async def cleanup(self) -> None:
        if self.__setup_progress_fade_task is not None:
            self.__setup_progress_fade_task.cancel()
            try:
                await self.__setup_progress_fade_task
            except asyncio.CancelledError:
                pass
            self.__setup_progress_fade_task = None

    #     if self.__engine_state_listener is not None:
    #         self.__engine_state_listener.remove()
    #         self.__engine_state_listener = None

        self.hide()

    #     while self._project_tabs.count() > 0:
    #         view = self._project_tabs.widget(0)
    #         if isinstance(view, ProjectView):
    #             await view.cleanup()
    #         self._project_tabs.removeTab(0)
        self.close()

    def createSetupProgress(self) -> SetupProgressWidget:
        assert self.__setup_progress == None

        self.__setup_progress = SetupProgressWidget(self.__main_area)
        self.__main_layout.addWidget(self.__setup_progress)

        return self.__setup_progress

    def deleteSetupProgress(self) -> None:
        if self.__setup_progress is not None and self.__setup_progress_fade_task is None:
            self.__setup_progress_fade_task = self.event_loop.create_task(
                self.__fadeSetupProgress())
            self.__setup_progress_fade_task.add_done_callback(self.__fadeSetupProgressDone)

    async def __fadeSetupProgress(self) -> None:
        eff = QtWidgets.QGraphicsOpacityEffect()
        self.__setup_progress.setGraphicsEffect(eff)

        eff.setOpacity(1.0)
        t0 = time.time()
        while eff.opacity() > 0.0:
            await asyncio.sleep(0.05, loop=self.event_loop)
            eff.setOpacity(1.0 - 2.0 * (time.time() - t0))

        self.__main_layout.removeWidget(self.__setup_progress)
        self.__setup_progress.setParent(None)
        self.__setup_progress = None

    def __fadeSetupProgressDone(self, task: asyncio.Task) -> None:
        if not task.cancelled():
            task.result()
        self.__setup_progress_fade_task = None

    def addProjectTab(self, title: str) -> ProjectTabPage:
        page = ProjectTabPage(parent=self.__project_tabs, context=self.context)
        idx = self.__project_tabs.addTab(page, title)
        self.__project_tabs.setCurrentIndex(idx)
        return page

    # def createStartView(self) -> QtWidgets.QWidget:
    #     view = QtWidgets.QWidget(self)

    #     gscene = QtWidgets.QGraphicsScene()
    #     gscene.addText("Some fancy logo goes here")

    #     gview = QtWidgets.QGraphicsView(self)
    #     gview.setBackgroundRole(QtGui.QPalette.Window)
    #     gview.setFrameShape(QtWidgets.QFrame.NoFrame)
    #     gview.setBackgroundBrush(QtGui.QBrush(Qt.NoBrush))
    #     gview.setScene(gscene)

    #     layout = QtWidgets.QVBoxLayout()
    #     layout.addWidget(gview)
    #     view.setLayout(layout)

    #     return view

    # def createActions(self) -> None:
    #     self._new_project_action = QtWidgets.QAction("New", self)
    #     self._new_project_action.setShortcut(QtGui.QKeySequence.New)
    #     self._new_project_action.setStatusTip("Create a new project")
    #     self._new_project_action.triggered.connect(self.onNewProject)

    #     self._open_project_action = QtWidgets.QAction("Open", self)
    #     self._open_project_action.setShortcut(QtGui.QKeySequence.Open)
    #     self._open_project_action.setStatusTip("Open an existing project")
    #     self._open_project_action.triggered.connect(self.onOpenProject)

    #     self._render_action = QtWidgets.QAction("Render", self)
    #     self._render_action.setStatusTip("Render project into an audio file.")
    #     self._render_action.triggered.connect(self.onRender)

    #     self._close_current_project_action = QtWidgets.QAction("Close", self)
    #     self._close_current_project_action.setShortcut(QtGui.QKeySequence.Close)
    #     self._close_current_project_action.setStatusTip("Close the current project")
    #     self._close_current_project_action.triggered.connect(self.onCloseCurrentProjectTab)
    #     self._close_current_project_action.setEnabled(False)

    #     self._undo_action = QtWidgets.QAction("Undo", self)
    #     self._undo_action.setShortcut(QtGui.QKeySequence.Undo)
    #     self._undo_action.setStatusTip("Undo most recent action")
    #     self._undo_action.triggered.connect(self.onUndo)

    #     self._redo_action = QtWidgets.QAction("Redo", self)
    #     self._redo_action.setShortcut(QtGui.QKeySequence.Redo)
    #     self._redo_action.setStatusTip("Redo most recently undone action")
    #     self._redo_action.triggered.connect(self.onRedo)

    #     self._clear_selection_action = QtWidgets.QAction("Clear", self)
    #     self._clear_selection_action.setStatusTip("Clear the selected items")
    #     self._clear_selection_action.triggered.connect(self.onClearSelection)

    #     self._copy_action = QtWidgets.QAction("Copy", self)
    #     self._copy_action.setShortcut(QtGui.QKeySequence.Copy)
    #     self._copy_action.setStatusTip("Copy current selected items to clipboard")
    #     self._copy_action.triggered.connect(self.onCopy)

    #     self._paste_as_link_action = QtWidgets.QAction("Paste as link", self)
    #     self._paste_as_link_action.setStatusTip(
    #         "Paste items from clipboard to current location as linked items")
    #     self._paste_as_link_action.triggered.connect(self.onPasteAsLink)

    #     self._paste_action = QtWidgets.QAction("Paste", self)
    #     self._paste_action.setShortcut(QtGui.QKeySequence.Paste)
    #     self._paste_action.setStatusTip("Paste items from clipboard to current location")
    #     self._paste_action.triggered.connect(self.onPaste)

    #     self._set_num_measures_action = QtWidgets.QAction("Set # measures", self)
    #     self._set_num_measures_action.setStatusTip("Set the number of measures in the project")
    #     self._set_num_measures_action.triggered.connect(self.onSetNumMeasures)

    #     self._set_bpm_action = QtWidgets.QAction("Set BPM", self)
    #     self._set_bpm_action.setStatusTip("Set the project's beats per second")
    #     self._set_bpm_action.triggered.connect(self.onSetBPM)

    #     self._restart_action = QtWidgets.QAction("Restart", self)
    #     self._restart_action.setShortcut("F5")
    #     self._restart_action.setShortcutContext(Qt.ApplicationShortcut)
    #     self._restart_action.setStatusTip("Restart the application")
    #     self._restart_action.triggered.connect(self.restart)

    #     self._restart_clean_action = QtWidgets.QAction("Restart clean", self)
    #     self._restart_clean_action.setShortcut("Ctrl+Shift+F5")
    #     self._restart_clean_action.setShortcutContext(Qt.ApplicationShortcut)
    #     self._restart_clean_action.setStatusTip("Restart the application in a clean state")
    #     self._restart_clean_action.triggered.connect(self.restart_clean)

    #     self._crash_action = QtWidgets.QAction("Crash", self)
    #     self._crash_action.triggered.connect(self.crash)

    #     self._dump_project_action = QtWidgets.QAction("Dump Project", self)
    #     self._dump_project_action.triggered.connect(self.dumpProject)

    #     self._about_action = QtWidgets.QAction("About", self)
    #     self._about_action.setStatusTip("Show the application's About box")
    #     self._about_action.triggered.connect(self.about)

    #     self._aboutqt_action = QtWidgets.QAction("About Qt", self)
    #     self._aboutqt_action.setStatusTip("Show the Qt library's About box")
    #     self._aboutqt_action.triggered.connect(self.qt_app.aboutQt)

    #     self._player_move_to_start_action = QtWidgets.QAction("Move to start", self)
    #     self._player_move_to_start_action.setIcon(QtGui.QIcon.fromTheme('media-skip-backward'))
    #     self._player_move_to_start_action.setShortcut(QtGui.QKeySequence('Home'))
    #     self._player_move_to_start_action.setShortcutContext(Qt.ApplicationShortcut)
    #     self._player_move_to_start_action.triggered.connect(lambda: self.onPlayerMoveTo('start'))

    #     self._player_move_to_end_action = QtWidgets.QAction("Move to end", self)
    #     self._player_move_to_end_action.setIcon(QtGui.QIcon.fromTheme('media-skip-forward'))
    #     self._player_move_to_end_action.setShortcut(QtGui.QKeySequence('End'))
    #     self._player_move_to_end_action.setShortcutContext(Qt.ApplicationShortcut)
    #     self._player_move_to_end_action.triggered.connect(lambda: self.onPlayerMoveTo('end'))

    #     self._player_move_to_prev_action = QtWidgets.QAction("Move to previous measure", self)
    #     self._player_move_to_prev_action.setIcon(QtGui.QIcon.fromTheme('media-seek-backward'))
    #     self._player_move_to_prev_action.setShortcut(QtGui.QKeySequence('PgUp'))
    #     self._player_move_to_prev_action.setShortcutContext(Qt.ApplicationShortcut)
    #     self._player_move_to_prev_action.triggered.connect(lambda: self.onPlayerMoveTo('prev'))

    #     self._player_move_to_next_action = QtWidgets.QAction("Move to next measure", self)
    #     self._player_move_to_next_action.setIcon(QtGui.QIcon.fromTheme('media-seek-forward'))
    #     self._player_move_to_next_action.setShortcut(QtGui.QKeySequence('PgDown'))
    #     self._player_move_to_next_action.setShortcutContext(Qt.ApplicationShortcut)
    #     self._player_move_to_next_action.triggered.connect(lambda: self.onPlayerMoveTo('next'))

    #     self._player_toggle_action = QtWidgets.QAction("Play", self)
    #     self._player_toggle_action.setIcon(QtGui.QIcon.fromTheme('media-playback-start'))
    #     self._player_toggle_action.setShortcut(QtGui.QKeySequence('Space'))
    #     self._player_toggle_action.setShortcutContext(Qt.ApplicationShortcut)
    #     self._player_toggle_action.triggered.connect(self.onPlayerToggle)

    #     self._player_loop_action = QtWidgets.QAction("Loop playback", self)
    #     self._player_loop_action.setIcon(QtGui.QIcon.fromTheme('media-playlist-repeat'))
    #     self._player_loop_action.setCheckable(True)
    #     self._player_loop_action.toggled.connect(self.onPlayerLoop)

    #     # self._show_pipeline_perf_monitor_action = QtWidgets.QAction(
    #     #     "Pipeline Performance Monitor", self)
    #     # self._show_pipeline_perf_monitor_action.setCheckable(True)
    #     # self._show_pipeline_perf_monitor_action.setChecked(
    #     #     self.app.pipeline_perf_monitor.isVisible())
    #     # self._show_pipeline_perf_monitor_action.toggled.connect(
    #     #     self.app.pipeline_perf_monitor.setVisible)
    #     # self.app.pipeline_perf_monitor.visibilityChanged.connect(
    #     #     self._show_pipeline_perf_monitor_action.setChecked)

    #     # self._show_stat_monitor_action = QtWidgets.QAction("Stat Monitor", self)
    #     # self._show_stat_monitor_action.setCheckable(True)
    #     # self._show_stat_monitor_action.setChecked(self.app.stat_monitor.isVisible())
    #     # self._show_stat_monitor_action.toggled.connect(
    #     #     self.app.stat_monitor.setVisible)
    #     # self.app.stat_monitor.visibilityChanged.connect(
    #     #     self._show_stat_monitor_action.setChecked)

    def createMenus(self) -> None:
        menu_bar = self.menuBar()

        self._project_menu = menu_bar.addMenu("Project")
    #     self._project_menu.addAction(self._new_project_action)
    #     self._project_menu.addAction(self._open_project_action)
    #     self._project_menu.addAction(self._close_current_project_action)
    #     self._project_menu.addSeparator()
    #     self._project_menu.addAction(self._render_action)
        self._project_menu.addSeparator()
        self._project_menu.addAction(self.app.show_instrument_library_action)
        self._project_menu.addSeparator()
        self._project_menu.addAction(self.app.show_settings_dialog_action)
        self._project_menu.addSeparator()
        self._project_menu.addAction(self.app.quit_action)

        self._edit_menu = menu_bar.addMenu("Edit")
    #     self._edit_menu.addAction(self._undo_action)
    #     self._edit_menu.addAction(self._redo_action)
    #     self._project_menu.addSeparator()
    #     self._edit_menu.addAction(self._clear_selection_action)
    #     self._edit_menu.addAction(self._copy_action)
    #     self._edit_menu.addAction(self._paste_action)
    #     self._edit_menu.addAction(self._paste_as_link_action)
    #     self._project_menu.addSeparator()
    #     #self._edit_menu.addAction(self._set_num_measures_action)
    #     self._edit_menu.addAction(self._set_bpm_action)

        self._view_menu = menu_bar.addMenu("View")

        if self.app.runtime_settings.dev_mode:
            menu_bar.addSeparator()
            self._dev_menu = menu_bar.addMenu("Dev")
    #         self._dev_menu.addAction(self._dump_project_action)
    #         self._dev_menu.addAction(self._restart_action)
    #         self._dev_menu.addAction(self._restart_clean_action)
    #         self._dev_menu.addAction(self._crash_action)
    #         #self._dev_menu.addAction(self._show_pipeline_perf_monitor_action)
    #         #self._dev_menu.addAction(self._show_stat_monitor_action)
    #         #self._dev_menu.addAction(self.app.profile_audio_thread_action)
    #         #self._dev_menu.addAction(self.app.dump_audioproc)

        menu_bar.addSeparator()

        self._help_menu = menu_bar.addMenu("Help")
        # self._help_menu.addAction(self._about_action)
        # self._help_menu.addAction(self._aboutqt_action)

    # def createToolBar(self) -> None:
    #     self.toolbar = QtWidgets.QToolBar()
    #     self.toolbar.setObjectName('toolbar:main')
    #     self.toolbar.addAction(self._player_toggle_action)
    #     self.toolbar.addAction(self._player_loop_action)
    #     self.toolbar.addSeparator()
    #     self.toolbar.addAction(self._player_move_to_start_action)
    #     #self.toolbar.addAction(self._player_move_to_prev_action)
    #     #self.toolbar.addAction(self._player_move_to_next_action)
    #     self.toolbar.addAction(self._player_move_to_end_action)

    #     self.addToolBar(Qt.TopToolBarArea, self.toolbar)

    # def createStatusBar(self) -> None:
    #     self.statusbar = QtWidgets.QStatusBar()

    #     self.pipeline_load = load_history.LoadHistoryWidget(100, 30)
    #     self.pipeline_load.setToolTip("Load of the playback engine.")
    #     self.statusbar.addPermanentWidget(self.pipeline_load)

    #     self.pipeline_status = QtWidgets.QLabel()
    #     self.statusbar.addPermanentWidget(self.pipeline_status)

    #     self.setStatusBar(self.statusbar)

    def storeState(self) -> None:
        logger.info("Saving current EditorWindow geometry.")
        self.app.settings.setValue('mainwindow/geometry', self.saveGeometry())
        self.app.settings.setValue('mainwindow/state', self.saveState())

    # def __engineStateChanged(self, engine_state: audioproc.EngineStateChange) -> None:
    #     show_status, show_load = False, False
    #     if engine_state.state == audioproc.EngineStateChange.SETUP:
    #         self.pipeline_status.setText("Starting engine...")
    #         show_status = True
    #     elif engine_state.state == audioproc.EngineStateChange.CLEANUP:
    #         self.pipeline_status.setText("Stopping engine...")
    #         show_status = True
    #     elif engine_state.state == audioproc.EngineStateChange.RUNNING:
    #         if engine_state.HasField('load'):
    #             self.pipeline_load.addValue(engine_state.load)
    #             show_load = True
    #         else:
    #             self.pipeline_status.setText("Engine running")
    #             show_status = True
    #     elif engine_state.state == audioproc.EngineStateChange.STOPPED:
    #         self.pipeline_status.setText("Engine stopped")
    #         show_status = True

    #     self.pipeline_status.setVisible(show_status)
    #     self.pipeline_load.setVisible(show_load)

    # def setInfoMessage(self, msg: str) -> None:
    #     self.statusbar.showMessage(msg)

    # def about(self) -> None:
    #     QtWidgets.QMessageBox.about(
    #         self, "About noisicaä",
    #         textwrap.dedent("""\
    #             Some text goes here...
    #             """))

    # def crash(self) -> None:
    #     raise RuntimeError("Something bad happened")

    # def dumpProject(self) -> None:
    #     view = self._project_tabs.currentWidget()
    #     self.call_async(view.project_client.dump())

    # def restart(self) -> None:
    #     raise RestartAppException("Restart requested by user.")

    # def restart_clean(self) -> None:
    #     raise RestartAppCleanException("Clean restart requested by user.")

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        logger.info("CloseEvent received")
        event.accept()
        self.app.quit()

    # def setCurrentProjectView(self, project_view: Optional[ProjectView]) -> None:
    #     if project_view == self._current_project_view:
    #         return

    #     if self._current_project_view is not None:
    #         self._current_project_view.playingChanged.disconnect(self.playingChanged)
    #         self._current_project_view.loopEnabledChanged.disconnect(self.loopEnabledChanged)

    #     if project_view is not None:
    #         project_view.playingChanged.connect(self.playingChanged)
    #         self.playingChanged.emit(project_view.playing())
    #         project_view.loopEnabledChanged.connect(self.loopEnabledChanged)
    #         self.loopEnabledChanged.emit(project_view.loopEnabled())

    #     self._current_project_view = project_view

    #     if project_view is not None:
    #         self.currentProjectChanged.emit(project_view.project)
    #     else:
    #         self.currentProjectChanged.emit(None)

    # def addProjectSetupView(self, project_connection: project_registry_lib.Project) -> int:
    #     widget = QtWidgets.QWidget()

    #     label = QtWidgets.QLabel(widget)
    #     label.setText("Opening project '%s'..." % project_connection.path)

    #     wheel = qprogressindicator.QProgressIndicator(widget)
    #     wheel.setMinimumSize(48, 48)
    #     wheel.setMaximumSize(48, 48)
    #     wheel.setAnimationDelay(100)
    #     wheel.startAnimation()

    #     layout = QtWidgets.QVBoxLayout()
    #     layout.addStretch(2)
    #     layout.addWidget(label, 0, Qt.AlignHCenter)
    #     layout.addSpacing(10)
    #     layout.addWidget(wheel, 0, Qt.AlignHCenter)
    #     layout.addStretch(3)
    #     widget.setLayout(layout)

    #     idx = self._project_tabs.addTab(widget, project_connection.name)
    #     self._project_tabs.setCurrentIndex(idx)
    #     self._main_area.setCurrentIndex(0)
    #     return idx

    # async def activateProjectView(
    #         self, idx: int, project_connection: project_registry_lib.Project) -> None:
    #     context = ui_base.CommonContext(app=self.app)
    #     view = ProjectView(project_connection=project_connection, context=context)
    #     await view.setup()

    #     self._project_tabs.insertTab(idx, view, project_connection.name)
    #     self._project_tabs.removeTab(idx + 1)

    #     self._project_tabs.setCurrentIndex(idx)
    #     self._close_current_project_action.setEnabled(True)

    # async def removeProjectView(self, project_connection: project_registry_lib.Project) -> None:
    #     for idx in range(self._project_tabs.count()):
    #         view = self._project_tabs.widget(idx)
    #         if isinstance(view, ProjectView) and view.project_connection is project_connection:
    #             self._project_tabs.removeTab(idx)
    #             if self._project_tabs.count() == 0:
    #                 self._main_area.setCurrentIndex(1)
    #             self._close_current_project_action.setEnabled(
    #                 self._project_tabs.count() > 0)

    #             await view.cleanup()
    #             break
    #     else:
    #         raise ValueError("No view for project found.")

    # def onCloseCurrentProjectTab(self) -> None:
    #     view = self._project_tabs.currentWidget()
    #     closed = view.close()
    #     if closed:
    #         self.call_async(self.app.removeProject(view.project_connection))

    # def onCurrentProjectTabChanged(self, idx: int) -> None:
    #     widget = self._project_tabs.widget(idx)
    #     if isinstance(widget, ProjectView):
    #         self.setCurrentProjectView(widget)
    #     else:
    #         self.setCurrentProjectView(None)

    # def onCloseProjectTab(self, idx: int) -> None:
    #     view = self._project_tabs.widget(idx)
    #     closed = view.close()
    #     if closed:
    #         self.call_async(self.app.removeProject(view.project_connection))

    # def getCurrentProjectView(self) -> ProjectView:
    #     return cast(ProjectView, self._project_tabs.currentWidget())

    # def listProjectViews(self) -> Iterator[ProjectView]:
    #     for idx in range(self._project_tabs.count()):
    #         yield cast(ProjectView, self._project_tabs.widget(idx))

    # def getCurrentProject(self) -> music.Project:
    #     view = self._project_tabs.currentWidget()
    #     return view.project

    # def onNewProject(self) -> None:
    #     path, _ = QtWidgets.QFileDialog.getSaveFileName(
    #         parent=self,
    #         caption="Select Project File",
    #         directory=constants.PROJECT_DIR,
    #         filter="All Files(*);;noisicaä Projects(*.noise)",
    #         initialFilter='noisicaä Projects(*.noise)',
    #     )
    #     if not path:
    #         return

    #     self.call_async(self.app.createProject(path))

    # def onOpenProject(self) -> None:
    #     path, _ = QtWidgets.QFileDialog.getOpenFileName(
    #         parent=self,
    #         caption="Open Project",
    #         directory=constants.PROJECT_DIR,
    #         filter="All Files(*);;noisicaä Projects(*.noise)",
    #         initialFilter='noisicaä Projects(*.noise)',
    #     )
    #     if not path:
    #         return

    #     self.call_async(self.app.openProject(path))

    # def onRender(self) -> None:
    #     view = self._project_tabs.currentWidget()
    #     view.onRender()

    # def onUndo(self) -> None:
    #     project_view = self.getCurrentProjectView()
    #     self.call_async(project_view.project.undo())

    # def onRedo(self) -> None:
    #     project_view = self.getCurrentProjectView()
    #     self.call_async(project_view.project.redo())

    # def onClearSelection(self) -> None:
    #     view = self._project_tabs.currentWidget()
    #     view.onClearSelection()

    # def onCopy(self) -> None:
    #     view = self._project_tabs.currentWidget()
    #     view.onCopy()

    # def onPaste(self) -> None:
    #     view = self._project_tabs.currentWidget()
    #     view.onPaste(mode='overwrite')

    # def onPasteAsLink(self) -> None:
    #     view = self._project_tabs.currentWidget()
    #     view.onPaste(mode='link')

    # def onSetNumMeasures(self) -> None:
    #     view = self._project_tabs.currentWidget()
    #     view.onSetNumMeasures()

    # def onSetBPM(self) -> None:
    #     view = self._project_tabs.currentWidget()
    #     view.onSetBPM()

    # def onPlayingChanged(self, playing: bool) -> None:
    #     if playing:
    #         self._player_toggle_action.setIcon(
    #             QtGui.QIcon.fromTheme('media-playback-pause'))
    #     else:
    #         self._player_toggle_action.setIcon(
    #             QtGui.QIcon.fromTheme('media-playback-start'))

    # def onLoopEnabledChanged(self, loop_enabled: bool) -> None:
    #     self._player_loop_action.setChecked(loop_enabled)

    # def onPlayerMoveTo(self, where: str) -> None:
    #     view = self._project_tabs.currentWidget()
    #     view.onPlayerMoveTo(where)

    # def onPlayerToggle(self) -> None:
    #     view = self._project_tabs.currentWidget()
    #     view.onPlayerToggle()

    # def onPlayerLoop(self, loop: bool) -> None:
    #     view = self._project_tabs.currentWidget()
    #     view.onPlayerLoop(loop)
