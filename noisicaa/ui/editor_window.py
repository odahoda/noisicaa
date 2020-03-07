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
import time
import traceback
import typing
from typing import cast, Any, Optional, Dict, Callable, Generator

from PyQt5.QtCore import Qt
from PyQt5 import QtCore
from PyQt5 import QtGui
from PyQt5 import QtWidgets

from noisicaa.core import storage
from noisicaa import audioproc
from . import project_view
from . import project_debugger
from . import ui_base
from . import qprogressindicator
from . import project_registry as project_registry_lib
from . import open_project_dialog
from . import engine_state as engine_state_lib

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
    def step(self, message: str) -> Generator:
        self.__step += 1
        self.__bar.setValue(self.__step)
        self.__message.setText("Initializing noisicaä: %s" % message)
        yield
        if self.__step == self.__num_steps:
            self.__message.setText("Initialization complete.")


class ProjectTabPage(ui_base.CommonMixin, QtWidgets.QWidget):
    currentPageChanged = QtCore.pyqtSignal(QtWidgets.QWidget)
    hasProjectView = QtCore.pyqtSignal(bool)

    def __init__(
            self, *,
            parent: QtWidgets.QTabWidget,
            engine_state: engine_state_lib.EngineState,
            **kwargs: Any
    ) -> None:
        super().__init__(parent=parent, **kwargs)

        self.__tab_widget = parent
        self.__engine_state = engine_state

        self.__page = None  # type: QtWidgets.QWidget
        self.__page_cleanup_func = None  # type: Callable[[], None]

        self.__project_view = None  # type: project_view.ProjectView
        self.__project_debugger = None  # type: project_debugger.ProjectDebugger

        self.__layout = QtWidgets.QVBoxLayout()
        self.__layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(self.__layout)

    def projectView(self) -> Optional[project_view.ProjectView]:
        return self.__project_view

    def setProjectView(self, name: str, view: project_view.ProjectView) -> None:
        self.__project_view = view
        self.__setPage(name, view)
        self.hasProjectView.emit(True)

    def projectDebugger(self) -> Optional[project_debugger.ProjectDebugger]:
        return self.__project_debugger

    def page(self) -> QtWidgets.QWidget:
        return self.__page

    def __setPage(
            self,
            name: str,
            page: QtWidgets.QWidget,
            cleanup_func: Callable[[], None] = None
    ) -> None:
        if self.__page is not None:
            self.__layout.removeWidget(self.__page)
            self.__page.setParent(None)
            self.__page = None
            if self.__page_cleanup_func is not None:
                self.__page_cleanup_func()
                self.__page_cleanup_func = None

        self.__tab_widget.setTabText(self.__tab_widget.indexOf(self), name)
        self.__layout.addWidget(page)
        self.__page = page
        self.__page_cleanup_func = cleanup_func
        self.currentPageChanged.emit(self.__page)

    def showOpenDialog(self) -> None:
        dialog = open_project_dialog.OpenProjectDialog(
            parent=self,
            context=self.context)
        dialog.projectSelected.connect(
            lambda project: self.call_async(self.openProject(project)))
        dialog.createProject.connect(
            lambda path: self.call_async(self.createProject(path)))
        dialog.createLoadtestProject.connect(
            lambda path, spec: self.call_async(self.createLoadtestProject(path, spec)))
        dialog.debugProject.connect(
            lambda path: self.call_async(self.__debugProject(path)))

        l1 = QtWidgets.QVBoxLayout()
        l1.addSpacing(32)
        l1.addWidget(dialog, 6)
        l1.addStretch(1)

        l2 = QtWidgets.QHBoxLayout()
        l2.addStretch(1)
        l2.addLayout(l1, 3)
        l2.addStretch(1)

        page = QtWidgets.QWidget(self)
        page.setObjectName('open-project')
        page.setLayout(l2)

        self.__setPage("Open project...", page, dialog.cleanup)

    def __projectErrorDialog(self, exc: Exception, message: str) -> None:
        logger.error(traceback.format_exc())

        dialog = QtWidgets.QMessageBox(self)
        dialog.setObjectName('project-open-error')
        dialog.setWindowTitle("noisicaä - Error")
        dialog.setIcon(QtWidgets.QMessageBox.Critical)
        dialog.setText(message)
        if isinstance(exc, storage.Error):
            dialog.setInformativeText(str(exc))
        else:
            dialog.setInformativeText("Internal error: %s" % type(exc).__name__)
        dialog.setDetailedText(traceback.format_exc())
        buttons = QtWidgets.QMessageBox.StandardButtons()
        buttons |= QtWidgets.QMessageBox.Close
        dialog.setStandardButtons(buttons)
        # TODO: Even with the size grip enabled, the dialog window is not resizable.
        # Might be a bug in Qt: https://bugreports.qt.io/browse/QTBUG-41932
        dialog.setSizeGripEnabled(True)
        dialog.setModal(True)
        dialog.finished.connect(lambda result: self.showOpenDialog())
        dialog.show()

    async def openProject(self, project: project_registry_lib.Project) -> None:
        self.showLoadSpinner(project.name, "Loading project \"%s\"..." % project.name)
        await self.app.setup_complete.wait()
        try:
            await project.open()

            view = project_view.ProjectView(
                project_connection=project,
                engine_state=self.__engine_state,
                context=self.context)
            view.setObjectName('project-view')
            try:
                await view.setup()
            except:
                await view.cleanup()
                raise
            self.setProjectView(project.name, view)

        except Exception as exc:  # pylint: disable=broad-except
            await project.close()
            self.__projectErrorDialog(
                exc, "Failed to open project \"%s\"." % project.name)

    async def createProject(self, path: str) -> None:
        project = project_registry_lib.Project(
            path=path, context=self.context)
        self.showLoadSpinner(project.name, "Creating project \"%s\"..." % project.name)
        await self.app.setup_complete.wait()
        try:
            await project.create()
            await self.app.project_registry.refresh()

            view = project_view.ProjectView(
                project_connection=project,
                engine_state=self.__engine_state,
                context=self.context)
            view.setObjectName('project-view')
            try:
                await view.setup()
            except:
                await view.cleanup()
                raise
            self.setProjectView(project.name, view)

        except Exception as exc:  # pylint: disable=broad-except
            await project.close()
            self.__projectErrorDialog(
                exc, "Failed to create project \"%s\"." % project.name)

    async def createLoadtestProject(self, path: str, spec: Dict[str, Any]) -> None:
        project = project_registry_lib.Project(
            path=path, context=self.context)
        self.showLoadSpinner(project.name, "Creating project \"%s\"..." % project.name)
        await self.app.setup_complete.wait()
        try:
            await project.create_loadtest(spec)
            await self.app.project_registry.refresh()

            view = project_view.ProjectView(
                project_connection=project,
                engine_state=self.__engine_state,
                context=self.context)
            view.setObjectName('project-view')
            try:
                await view.setup()
            except:
                await view.cleanup()
                raise
            self.setProjectView(project.name, view)

        except Exception as exc:  # pylint: disable=broad-except
            await project.close()
            self.__projectErrorDialog(
                exc, "Failed to create project \"%s\"." % project.name)

    async def __debugProject(self, project: project_registry_lib.Project) -> None:
        self.showLoadSpinner(project.name, "Loading project \"%s\"..." % project.name)
        await self.app.setup_complete.wait()
        debugger = project_debugger.ProjectDebugger(project=project, context=self.context)
        debugger.setObjectName('project-debugger')
        await debugger.setup()
        self.__project_debugger = debugger
        self.__setPage(project.name, debugger)

    def showLoadSpinner(self, name: str, message: str) -> None:
        page = QtWidgets.QWidget(self)
        page.setObjectName('load-spinner')

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

        self.__setPage(name, page)

    async def closeProject(self) -> None:
        assert self.__project_view
        project = self.__project_view.project_connection
        self.showLoadSpinner(project.name, "Closing project \"%s\"..." % project.name)
        await self.__project_view.cleanup()
        self.__project_view = None
        await project.close()
        self.hasProjectView.emit(False)
        self.showOpenDialog()

    async def closeDebugger(self) -> None:
        assert self.__project_debugger
        project = self.__project_debugger.project
        self.showLoadSpinner(project.name, "Closing project \"%s\"..." % project.name)
        await self.__project_debugger.cleanup()
        self.__project_debugger = None
        self.showOpenDialog()


class EditorWindow(ui_base.CommonMixin, QtWidgets.QMainWindow):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.__engine_state = engine_state_lib.EngineState(self)
        self.__engine_state_listener = None  # type: core.Listener[audioproc.EngineStateChange]

        self.setWindowTitle("noisicaä")
        self.resize(1200, 800)

        self.__setup_progress = None  # type: SetupProgressWidget
        self.__setup_progress_fade_task = None  # type: asyncio.Task

        self.createActions()
        self.createMenus()

        self.__project_tabs = QtWidgets.QTabWidget(self)
        self.__project_tabs.setObjectName('project-tabs')
        self.__project_tabs.setTabBarAutoHide(True)
        self.__project_tabs.setUsesScrollButtons(True)
        self.__project_tabs.setTabsClosable(True)
        self.__project_tabs.setMovable(True)
        self.__project_tabs.setDocumentMode(True)
        self.__project_tabs.tabCloseRequested.connect(
            lambda idx: self.call_async(self.onCloseProjectTab(idx)))

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
        self.show()

    async def cleanup(self) -> None:
        self.hide()

        if self.__setup_progress_fade_task is not None:
            self.__setup_progress_fade_task.cancel()
            try:
                await self.__setup_progress_fade_task
            except asyncio.CancelledError:
                pass
            self.__setup_progress_fade_task = None

        if self.__engine_state_listener is not None:
            self.__engine_state_listener.remove()
            self.__engine_state_listener = None

        while self.__project_tabs.count() > 0:
            tab = cast(ProjectTabPage, self.__project_tabs.widget(0))
            view = tab.projectView()
            if view is not None:
                await view.cleanup()
            self.__project_tabs.removeTab(0)

    def audioprocReady(self) -> None:
        self.__engine_state_listener = self.audioproc_client.engine_state_changed.add(
            self.__engine_state.updateState)

    def createSetupProgress(self) -> SetupProgressWidget:
        assert self.__setup_progress is None

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

    def addProjectTab(self) -> ProjectTabPage:
        page = ProjectTabPage(
            parent=self.__project_tabs,
            engine_state=self.__engine_state,
            context=self.context)
        idx = self.__project_tabs.addTab(page, '')
        self.__project_tabs.setCurrentIndex(idx)
        return page

    def createActions(self) -> None:
        self._render_action = QtWidgets.QAction("Render", self)
        self._render_action.setStatusTip("Render project into an audio file.")
        self._render_action.triggered.connect(self.onRender)

        self._close_current_project_action = QtWidgets.QAction("Close", self)
        self._close_current_project_action.setObjectName('close-project')
        self._close_current_project_action.setShortcut(QtGui.QKeySequence.Close)
        self._close_current_project_action.setStatusTip("Close the current project")
        self._close_current_project_action.triggered.connect(self.onCloseCurrentProject)

        self._undo_action = QtWidgets.QAction("Undo", self)
        self._undo_action.setShortcut(QtGui.QKeySequence.Undo)
        self._undo_action.setStatusTip("Undo most recent action")
        self._undo_action.triggered.connect(self.onUndo)

        self._redo_action = QtWidgets.QAction("Redo", self)
        self._redo_action.setShortcut(QtGui.QKeySequence.Redo)
        self._redo_action.setStatusTip("Redo most recently undone action")
        self._redo_action.triggered.connect(self.onRedo)

        self._set_bpm_action = QtWidgets.QAction("Set BPM", self)
        self._set_bpm_action.setStatusTip("Set the project's beats per second")
        self._set_bpm_action.triggered.connect(self.onSetBPM)

    def createMenus(self) -> None:
        menu_bar = self.menuBar()

        self._project_menu = menu_bar.addMenu("Project")
        self._project_menu.addAction(self.app.new_project_action)
        self._project_menu.addAction(self.app.open_project_action)
        self._project_menu.addAction(self._close_current_project_action)
        self._project_menu.addSeparator()
        self._project_menu.addAction(self._render_action)
        self._project_menu.addSeparator()
        self._project_menu.addAction(self.app.show_instrument_library_action)
        self._project_menu.addSeparator()
        self._project_menu.addAction(self.app.show_settings_dialog_action)
        self._project_menu.addSeparator()
        self._project_menu.addAction(self.app.quit_action)

        self._edit_menu = menu_bar.addMenu("Edit")
        self._edit_menu.addAction(self._undo_action)
        self._edit_menu.addAction(self._redo_action)
        self._project_menu.addSeparator()
        self._edit_menu.addAction(self.app.clipboard.copy_action)
        self._edit_menu.addAction(self.app.clipboard.cut_action)
        self._edit_menu.addAction(self.app.clipboard.paste_action)
        self._edit_menu.addAction(self.app.clipboard.paste_as_link_action)
        self._project_menu.addSeparator()
        #self._edit_menu.addAction(self._set_num_measures_action)
        self._edit_menu.addAction(self._set_bpm_action)

        self._view_menu = menu_bar.addMenu("View")

        if self.app.runtime_settings.dev_mode:
            menu_bar.addSeparator()
            self._dev_menu = menu_bar.addMenu("Dev")
            self._dev_menu.addAction(self.app.restart_action)
            self._dev_menu.addAction(self.app.restart_clean_action)
            self._dev_menu.addAction(self.app.crash_action)
            self._dev_menu.addAction(self.app.show_pipeline_perf_monitor_action)
            self._dev_menu.addAction(self.app.show_stat_monitor_action)
            self._dev_menu.addAction(self.app.profile_audio_thread_action)
            self._dev_menu.addAction(self.app.dump_audioproc_action)

        menu_bar.addSeparator()

        self._help_menu = menu_bar.addMenu("Help")
        self._help_menu.addAction(self.app.about_action)
        self._help_menu.addAction(self.app.aboutqt_action)

    def storeState(self) -> None:
        logger.info("Saving current EditorWindow geometry.")
        self.app.settings.setValue('mainwindow/geometry', self.saveGeometry())
        self.app.settings.setValue('mainwindow/state', self.saveState())

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        logger.info("CloseEvent received")
        event.ignore()
        self.call_async(self.app.deleteWindow(self))

    def onCloseCurrentProject(self) -> None:
        idx = self.__project_tabs.currentIndex()
        tab = cast(ProjectTabPage, self.__project_tabs.widget(idx))
        if tab.projectView() is not None:
            self.call_async(tab.closeProject())
        elif tab.projectDebugger() is not None:
            self.call_async(tab.closeDebugger())
        if self.__project_tabs.count() > 1:
            self.__project_tabs.removeTab(idx)

    async def onCloseProjectTab(self, idx: int) -> None:
        tab = cast(ProjectTabPage, self.__project_tabs.widget(idx))
        if tab.projectView() is not None:
            await tab.closeProject()
        if tab.projectDebugger() is not None:
            await tab.closeDebugger()
        self.__project_tabs.removeTab(idx)

    def getCurrentProjectView(self) -> Optional[project_view.ProjectView]:
        tab = cast(ProjectTabPage, self.__project_tabs.currentWidget())
        return tab.projectView()

    def onRender(self) -> None:
        view = self.getCurrentProjectView()
        if view is not None:
            view.onRender()

    def onUndo(self) -> None:
        view = self.getCurrentProjectView()
        if view is not None:
            self.call_async(view.project.undo())

    def onRedo(self) -> None:
        view = self.getCurrentProjectView()
        if view is not None:
            self.call_async(view.project.redo())

    def onSetBPM(self) -> None:
        view = self.getCurrentProjectView()
        if view is not None:
            view.onSetBPM()
