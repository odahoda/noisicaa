#!/usr/bin/python3

# Still need to figure out how to pass around the app reference, disable
# message "Access to a protected member .. of a client class"
# pylint: disable=W0212

import logging
import textwrap

from PyQt5.QtCore import Qt
from PyQt5 import QtCore
from PyQt5 import QtGui
from PyQt5 import QtWidgets

from ..exceptions import RestartAppException, RestartAppCleanException
from .command_shell import CommandShell
from .settings import SettingsDialog
from .project_view import ProjectView
from .dock_widget import DockWidget
from ..importers.abc import ABCImporter, ImporterError
from .load_history import LoadHistoryWidget
from . import ui_base
from . import instrument_library
from . import selection_set

logger = logging.getLogger(__name__)


class CommandShellDockWidget(DockWidget):
    def __init__(self, app, parent):
        super().__init__(
            app=app,
            parent=parent,
            identifier='command_shell',
            title="Command Shell",
            allowed_areas=Qt.AllDockWidgetAreas,
            initial_area=Qt.BottomDockWidgetArea,
            initial_visible=False)
        command_shell = CommandShell(parent=self)
        self.setWidget(command_shell)


class EditorWindow(ui_base.CommonMixin, QtWidgets.QMainWindow):
    # Could not figure out how to define a signal that takes either an instance
    # of a specific class or None.
    currentProjectChanged = QtCore.pyqtSignal(object)
    currentSheetChanged = QtCore.pyqtSignal(object)
    currentTrackChanged = QtCore.pyqtSignal(object)

    projectListChanged = QtCore.pyqtSignal()

    def __init__(self, app):
        super().__init__(app=app)

        self._docks = []
        self._settings_dialog = SettingsDialog(self.app, self)

        self._instrument_library_dialog = instrument_library.InstrumentLibraryDialog(
            **self.context, parent=self)

        self._current_project_view = None

        self.setWindowTitle("noisicaä")
        self.resize(1200, 800)

        self.createActions()
        self.createMenus()
        self.createToolBar()
        self.createStatusBar()
        self.createDockWidgets()

        self._project_tabs = QtWidgets.QTabWidget(self)
        self._project_tabs.setTabBarAutoHide(True)
        self._project_tabs.setUsesScrollButtons(True)
        self._project_tabs.setTabsClosable(True)
        self._project_tabs.setMovable(True)
        self._project_tabs.setDocumentMode(True)
        self._project_tabs.tabCloseRequested.connect(self.onCloseProjectTab)
        self._project_tabs.currentChanged.connect(self.onCurrentProjectTabChanged)

        self._start_view = self.createStartView()

        self._main_area = QtWidgets.QStackedWidget(self)
        self._main_area.addWidget(self._project_tabs)
        self._main_area.addWidget(self._start_view)
        self._main_area.setCurrentIndex(1)
        self.setCentralWidget(self._main_area)

        self.restoreGeometry(
            self.app.settings.value('mainwindow/geometry', b''))
        self.restoreState(
            self.app.settings.value('mainwindow/state', b''))

    async def setup(self):
        await self._instrument_library_dialog.setup()

    async def cleanup(self):
        await self._instrument_library_dialog.cleanup()

        self.hide()

        while self._project_tabs.count() > 0:
            view = self._project_tabs.widget(0)
            view.close()
            self._project_tabs.removeTab(0)
        self._settings_dialog.close()
        self.close()

    def createStartView(self):
        view = QtWidgets.QWidget(self)

        gscene = QtWidgets.QGraphicsScene()
        gscene.addText("Some fancy logo goes here")

        gview = QtWidgets.QGraphicsView(self)
        gview.setBackgroundRole(QtGui.QPalette.Window)
        gview.setFrameShape(QtWidgets.QFrame.NoFrame)
        gview.setBackgroundBrush(QtGui.QBrush(Qt.NoBrush))
        gview.setScene(gscene)

        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(gview)
        view.setLayout(layout)

        return view

    def createActions(self):
        self._new_project_action = QtWidgets.QAction(
            "New", self,
            shortcut=QtGui.QKeySequence.New,
            statusTip="Create a new project",
            triggered=self.onNewProject)

        self._open_project_action = QtWidgets.QAction(
            "Open", self,
            shortcut=QtGui.QKeySequence.Open,
            statusTip="Open an existing project",
            triggered=self.onOpenProject)

        self._import_action = QtWidgets.QAction(
            "Import", self,
            statusTip="Import a file into the current project.",
            triggered=self.onImport)

        self._render_action = QtWidgets.QAction(
            "Render", self,
            statusTip="Render sheet into an audio file.",
            triggered=self.onRender)

        self._save_project_action = QtWidgets.QAction(
            "Save", self,
            shortcut=QtGui.QKeySequence.Save,
            statusTip="Save the current project",
            triggered=self.onSaveProject)

        self._close_current_project_action = QtWidgets.QAction(
            "Close", self,
            shortcut=QtGui.QKeySequence.Close,
            statusTip="Close the current project",
            triggered=self.onCloseCurrentProjectTab,
            enabled=False)

        self._undo_action = QtWidgets.QAction(
            "Undo", self,
            shortcut=QtGui.QKeySequence.Undo,
            statusTip="Undo most recent action",
            triggered=self.onUndo)

        self._redo_action = QtWidgets.QAction(
            "Redo", self,
            shortcut=QtGui.QKeySequence.Redo,
            statusTip="Redo most recently undone action",
            triggered=self.onRedo)

        self._copy_action = QtWidgets.QAction(
            "Copy", self,
            shortcut=QtGui.QKeySequence.Copy,
            statusTip="Copy current selected items to clipboard",
            triggered=self.onCopy)

        self._paste_as_link_action = QtWidgets.QAction(
            "Paste as link", self,
            shortcut=QtGui.QKeySequence.Paste,
            statusTip=("Paste items from clipboard to current location as"
                       " linked items"),
            triggered=self.onPasteAsLink)

        self._restart_action = QtWidgets.QAction(
            "Restart", self,
            shortcut="F5", shortcutContext=Qt.ApplicationShortcut,
            statusTip="Restart the application", triggered=self.restart)

        self._restart_clean_action = QtWidgets.QAction(
            "Restart clean", self,
            shortcut="Ctrl+Shift+F5", shortcutContext=Qt.ApplicationShortcut,
            statusTip="Restart the application in a clean state",
            triggered=self.restart_clean)

        self._quit_action = QtWidgets.QAction(
            "Quit", self,
            shortcut=QtGui.QKeySequence.Quit,
            shortcutContext=Qt.ApplicationShortcut,
            statusTip="Quit the application", triggered=self.quit)

        self._crash_action = QtWidgets.QAction(
            "Crash", self,
            triggered=self.crash)

        self._dump_project_action = QtWidgets.QAction(
            "Dump Project", self,
            triggered=self.dumpProject)

        self._about_action = QtWidgets.QAction(
            "About", self,
            statusTip="Show the application's About box",
            triggered=self.about)

        self._aboutqt_action = QtWidgets.QAction(
            "About Qt", self,
            statusTip="Show the Qt library's About box",
            triggered=self.app.aboutQt)

        self._open_settings_action = QtWidgets.QAction(
            "Settings", self,
            statusTip="Open the settings dialog.",
            triggered=self.openSettings)

        self._open_instrument_library_action = QtWidgets.QAction(
            "Instrument Library", self,
            statusTip="Open the instrument library dialog.",
            triggered=self.openInstrumentLibrary)

        self._player_start_action = QtWidgets.QAction(
            QtGui.QIcon.fromTheme('media-playback-start'),
            "Play",
            self, triggered=self.onPlayerStart)
        self._player_pause_action = QtWidgets.QAction(
            QtGui.QIcon.fromTheme('media-playback-pause'),
            "Pause",
            self, triggered=self.onPlayerPause)
        self._player_stop_action = QtWidgets.QAction(
            QtGui.QIcon.fromTheme('media-playback-stop'),
            "Stop",
            self, triggered=self.onPlayerStop)

        self._show_pipeline_perf_monitor_action = QtWidgets.QAction(
            "Pipeline Performance Monitor", self,
            checkable=True,
            checked=self.app.pipeline_perf_monitor.isVisible())
        self._show_pipeline_perf_monitor_action.toggled.connect(
            self.app.pipeline_perf_monitor.setVisible)
        self.app.pipeline_perf_monitor.visibilityChanged.connect(
            self._show_pipeline_perf_monitor_action.setChecked)

        if self.app.pipeline_graph_monitor is not None:
            self._show_pipeline_graph_monitor_action = QtWidgets.QAction(
                "Pipeline Graph Monitor", self,
                checkable=True,
                checked=self.app.pipeline_graph_monitor.isVisible())
            self._show_pipeline_graph_monitor_action.toggled.connect(
                self.app.pipeline_graph_monitor.setVisible)
            self.app.pipeline_graph_monitor.visibilityChanged.connect(
                self._show_pipeline_graph_monitor_action.setChecked)

        self._show_stat_monitor_action = QtWidgets.QAction(
            "Stat Monitor", self,
            checkable=True,
            checked=self.app.stat_monitor.isVisible())
        self._show_stat_monitor_action.toggled.connect(
            self.app.stat_monitor.setVisible)
        self.app.stat_monitor.visibilityChanged.connect(
            self._show_stat_monitor_action.setChecked)

    def createMenus(self):
        menu_bar = self.menuBar()

        self._project_menu = menu_bar.addMenu("Project")
        self._project_menu.addAction(self._new_project_action)
        self._project_menu.addAction(self._open_project_action)
        self._project_menu.addAction(self._save_project_action)
        self._project_menu.addAction(self._close_current_project_action)
        self._project_menu.addSeparator()
        self._project_menu.addAction(self._import_action)
        self._project_menu.addAction(self._render_action)
        self._project_menu.addSeparator()
        self._project_menu.addAction(self._open_instrument_library_action)
        self._project_menu.addSeparator()
        self._project_menu.addAction(self._open_settings_action)
        self._project_menu.addSeparator()
        self._project_menu.addAction(self._quit_action)

        self._edit_menu = menu_bar.addMenu("Edit")
        self._edit_menu.addAction(self._undo_action)
        self._edit_menu.addAction(self._redo_action)
        self._project_menu.addSeparator()
        self._edit_menu.addAction(self._copy_action)
        self._edit_menu.addAction(self._paste_as_link_action)

        self._view_menu = menu_bar.addMenu("View")

        if self.app.runtime_settings.dev_mode:
            menu_bar.addSeparator()
            self._dev_menu = menu_bar.addMenu("Dev")
            self._dev_menu.addAction(self._dump_project_action)
            self._dev_menu.addAction(self._restart_action)
            self._dev_menu.addAction(self._restart_clean_action)
            self._dev_menu.addAction(self._crash_action)
            self._dev_menu.addAction(self.app.show_edit_areas_action)
            self._dev_menu.addAction(self._show_pipeline_perf_monitor_action)
            if self.app.pipeline_graph_monitor is not None:
                self._dev_menu.addAction(
                    self._show_pipeline_graph_monitor_action)
            self._dev_menu.addAction(self._show_stat_monitor_action)

        menu_bar.addSeparator()

        self._help_menu = menu_bar.addMenu("Help")
        self._help_menu.addAction(self._about_action)
        self._help_menu.addAction(self._aboutqt_action)

    def createToolBar(self):
        self.toolbar = QtWidgets.QToolBar()
        self.toolbar.setObjectName('toolbar:main')
        self.toolbar.addAction(self._player_start_action)
        #elf.toolbar.addAction(self._player_pause_action)
        self.toolbar.addAction(self._player_stop_action)

        self.addToolBar(Qt.TopToolBarArea, self.toolbar)

    def createStatusBar(self):
        self.statusbar = QtWidgets.QStatusBar()

        # self.pipeline_load = LoadHistoryWidget(100, 30)
        # self.pipeline_load.setToolTip("Load of the playback engine.")
        # self.statusbar.addPermanentWidget(self.pipeline_load)

        self.pipeline_status = QtWidgets.QLabel()
        self.statusbar.addPermanentWidget(self.pipeline_status)

        self.setStatusBar(self.statusbar)

    def createDockWidgets(self):
        self._docks.append(CommandShellDockWidget(self.app, self))

    def storeState(self):
        logger.info("Saving current EditorWindow geometry.")
        self.app.settings.setValue('mainwindow/geometry', self.saveGeometry())
        self.app.settings.setValue('mainwindow/state', self.saveState())

        self._settings_dialog.storeState()

    def setInfoMessage(self, msg):
        self.statusbar.showMessage(msg)

    def updateView(self):
        for idx in range(self._project_tabs.count()):
            project_view = self._project_tabs.widget(idx)
            project_view.updateView()

    def about(self):
        QtWidgets.QMessageBox.about(
            self, "About noisicaä",
            textwrap.dedent("""\
                Some text goes here...
                """))

    def crash(self):
        raise RuntimeError("Something bad happened")

    def dumpProject(self):
        view = self._project_tabs.currentWidget()
        self.call_async(view.project_client.dump())

    def restart(self):
        raise RestartAppException("Restart requested by user.")

    def restart_clean(self):
        raise RestartAppCleanException("Clean restart requested by user.")

    def quit(self):
        self.app.quit()

    def openSettings(self):
        self._settings_dialog.show()
        self._settings_dialog.activateWindow()

    def openInstrumentLibrary(self):
        self._instrument_library_dialog.show()
        self._instrument_library_dialog.activateWindow()

    def closeEvent(self, event):
        logger.info("CloseEvent received")

        for idx in range(self._project_tabs.count()):
            view = self._project_tabs.widget(idx)
            closed = view.close()
            if not closed:
                event.ignore()
                return
            self._project_tabs.removeTab(idx)

        event.accept()
        self.app.quit()

    def setCurrentProjectView(self, project_view):
        if project_view == self._current_project_view:
            return

        if self._current_project_view is not None:
            self._current_project_view.currentSheetChanged.disconnect(
                self.currentSheetChanged)

        if project_view is not None:
            project_view.currentSheetChanged.connect(
                self.currentSheetChanged)

        self._current_project_view = project_view

        if project_view is not None:
            self.currentProjectChanged.emit(project_view.project)
            self.currentSheetChanged.emit(project_view.currentSheetView().sheet)
        else:
            self.currentProjectChanged.emit(None)
            self.currentSheetChanged.emit(None)

    async def addProjectView(self, project_connection):
        view = ProjectView(
            selection_set=selection_set.SelectionSet(),
            project_connection=project_connection,
            **self.context)
        await view.setup()

        idx = self._project_tabs.addTab(view, project_connection.name)

        self._project_tabs.setCurrentIndex(idx)
        self._close_current_project_action.setEnabled(True)
        self._main_area.setCurrentIndex(0)

        self.projectListChanged.emit()

    async def removeProjectView(self, project_connection):
        for idx in range(self._project_tabs.count()):
            view = self._project_tabs.widget(idx)
            if view.project_connection is project_connection:
                self._project_tabs.removeTab(idx)
                if self._project_tabs.count() == 0:
                    self._main_area.setCurrentIndex(1)
                self._close_current_project_action.setEnabled(
                    self._project_tabs.count() > 0)

                await view.cleanup()
                self.projectListChanged.emit()
                break
        else:
            raise ValueError("No view for project found.")

    def onCloseCurrentProjectTab(self):
        view = self._project_tabs.currentWidget()
        closed = view.close()
        if closed:
            self.call_async(
                    self.app.removeProject(view.project_connection))

    def onCurrentProjectTabChanged(self, idx):
        project_view = self._project_tabs.widget(idx)
        self.setCurrentProjectView(project_view)

    def onCloseProjectTab(self, idx):
        view = self._project_tabs.widget(idx)
        closed = view.close()
        if closed:
            self.call_async(
                self.app.removeProject(view.project_connection))

    def getCurrentProjectView(self):
        return self._project_tabs.currentWidget()

    def listProjectViews(self):
        for idx in range(self._project_tabs.count()):
            yield self._project_tabs.widget(idx)

    def getCurrentProject(self):
        view = self._project_tabs.currentWidget()
        return view.project

    def onNewProject(self):
        path, open_filter = QtWidgets.QFileDialog.getSaveFileName(
            parent=self,
            caption="Select Project File",
            #directory=self.ui_state.get(
            #    'instruments_add_dialog_path', ''),
            filter="All Files (*);;noisicaä Projects (*.emp)",
            #initialFilter=self.ui_state.get(
            #'instruments_add_dialog_path', ''),
        )
        if not path:
            return

        self.call_async(self.app.createProject(path))

    def onOpenProject(self):
        path, open_filter = QtWidgets.QFileDialog.getOpenFileName(
            parent=self,
            caption="Open Project",
            #directory=self.ui_state.get(
            #'instruments_add_dialog_path', ''),
            filter="All Files (*);;noisicaä Projects (*.emp)",
            #initialFilter=self.ui_state.get(
            #    'instruments_add_dialog_path', ''),
        )
        if not path:
            return

        self.call_async(self.app.openProject(path))

    def onImport(self):
        path, open_filter = QtWidgets.QFileDialog.getOpenFileName(
            parent=self,
            caption="Import file",
            #directory=self.ui_state.get(
            #'instruments_add_dialog_path', ''),
            filter="All Files (*);;ABC (*.abc)",
            #initialFilter=self.ui_state.get(
            #    'instruments_add_dialog_path', ''),
        )
        if not path:
            return

        importer = ABCImporter()
        try:
            importer.import_file(path, self.getCurrentProject())
        except ImporterError as exc:
            errorbox = QtWidgets.QMessageBox()
            errorbox.setWindowTitle("Failed to import file")
            errorbox.setText("Failed import file from path %s." % path)
            errorbox.setInformativeText(str(exc))
            errorbox.setIcon(QtWidgets.QMessageBox.Warning)
            errorbox.addButton("Close", QtWidgets.QMessageBox.AcceptRole)
            errorbox.exec_()

    def onRender(self):
        view = self._project_tabs.currentWidget()
        view.onRender()

    def onSaveProject(self):
        project = self.getCurrentProject()
        project.create_checkpoint()

    def onUndo(self):
        project_view = self.getCurrentProjectView()
        self.call_async(project_view.project_client.undo())

    def onRedo(self):
        project_view = self.getCurrentProjectView()
        self.call_async(project_view.project_client.redo())

    def onCopy(self):
        view = self._project_tabs.currentWidget()
        view.onCopy()

    def onPasteAsLink(self):
        view = self._project_tabs.currentWidget()
        view.onPasteAsLink()

    def onPlayerStart(self):
        view = self._project_tabs.currentWidget()
        view.onPlayerStart()

    def onPlayerPause(self):
        view = self._project_tabs.currentWidget()
        view.onPlayerPause()

    def onPlayerStop(self):
        view = self._project_tabs.currentWidget()
        view.onPlayerStop()
