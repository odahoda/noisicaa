#!/usr/bin/python3

import logging
import os
import sys
import traceback

from PyQt5.QtCore import QSettings, QByteArray
from PyQt5.QtGui import QKeySequence
from PyQt5.QtWidgets import (
    QAction,
    QMessageBox,
    QApplication,
    QStyleFactory,
    QFileDialog,
)

from noisicaa import music
from noisicaa import devices
from ..exceptions import RestartAppException, RestartAppCleanException
from ..constants import EXIT_EXCEPTION, EXIT_RESTART, EXIT_RESTART_CLEAN
from .editor_window import EditorWindow
from ..instr.library import InstrumentLibrary

from . import project_registry


logger = logging.getLogger('ui.editor_app')


class ExceptHook(object):
    def __init__(self, app):
        self.app = app

    def __call__(self, exc_type, exc_value, tb):
        if issubclass(exc_type, RestartAppException):
            self.app.quit(EXIT_RESTART)
            return
        if issubclass(exc_type, RestartAppCleanException):
            self.app.quit(EXIT_RESTART_CLEAN)
            return

        msg = ''.join(traceback.format_exception(exc_type, exc_value, tb))

        logger.error("Uncaught exception:\n%s", msg)
        self._show_crash_dialog(msg)

        os._exit(EXIT_EXCEPTION)

    def _show_crash_dialog(self, msg):
        errorbox = QMessageBox()
        errorbox.setWindowTitle("noisicaä crashed")
        errorbox.setText("Uncaught exception")
        errorbox.setInformativeText(msg)
        errorbox.setIcon(QMessageBox.Critical)
        errorbox.addButton("Exit", QMessageBox.AcceptRole)
        errorbox.exec_()


class BaseEditorApp(QApplication):
    def __init__(self, process, runtime_settings, settings=None):
        super().__init__(['noisicaä'])

        self.process = process

        self.runtime_settings = runtime_settings

        if settings is None:
            settings = QSettings('odahoda.de', 'noisicaä')
            if runtime_settings.start_clean:
                settings.clear()
        self.settings = settings
        self.dumpSettings()

        self.setQuitOnLastWindowClosed(False)

        self.default_style = None

        self.project_registry = None
        self.sequencer = None
        self.midi_hub = None

    async def setup(self):
        self.default_style = self.style().objectName()

        style_name = self.settings.value('appearance/qtStyle', '')
        if style_name:
            style = QStyleFactory.create(style_name)
            self.setStyle(style)

        self.project_registry = project_registry.ProjectRegistry(
            self.process.event_loop, self.process.manager)

        self.sequencer = self.createSequencer()

        self.midi_hub = self.createMidiHub()
        self.midi_hub.start()

        self.new_project_action = QAction(
            "New", self,
            shortcut=QKeySequence.New,
            statusTip="Create a new project",
            triggered=self.newProject)

        self.show_edit_areas_action = QAction(
            "Show Edit Areas", self,
            checkable=True,
            triggered=self.onShowEditAreasChanged)
        self.show_edit_areas_action.setChecked(
            int(self.settings.value('dev/show_edit_areas', '0')))

    async def cleanup(self):
        logger.info("Cleaning up.")
        if self.midi_hub is not None:
            self.midi_hub.stop()
            self.midi_hub = None

        if self.sequencer is not None:
            self.sequencer.close()
            self.sequencer = None

    def quit(self, exit_code=0):
        self.process.quit(exit_code)

    def createSequencer(self):
        return None

    def createMidiHub(self):
        return devices.MidiHub(self.sequencer)

    def dumpSettings(self):
        for key in self.settings.allKeys():
            value = self.settings.value(key)
            if isinstance(value, (bytes, QByteArray)):
                value = '[%d bytes]' % len(value)
            logger.info('%s: %s', key, value)

    def onShowEditAreasChanged(self):
        self.settings.setValue(
            'dev/show_edit_areas', int(self.show_edit_areas_action.isChecked()))
        self.win.updateView()

    @property
    def showEditAreas(self):
        return (self.runtime_settings.dev_mode
                and self.show_edit_areas_action.isChecked())

    def addProject(self, project):
        #self._projects.append(project)
        self.win.addProjectView(project)

        self.settings.setValue(
            'opened_projects',
            [project.path for project in self._projects if project.path])

    def removeProject(self, project):
        self.win.removeProjectView(project)
        #self._projects.remove(project)

        self.settings.setValue(
            'opened_projects',
            [project.path for project in self._projects if project.path])

    def newProject(self):
        path, open_filter = QFileDialog.getSaveFileName(
            parent=self.win,
            caption="Select Project File",
            #directory=self.ui_state.get(
            #    'instruments_add_dialog_path', ''),
            filter="All Files (*);;noisicaä Projects (*.emp)",
            #initialFilter=self.ui_state.get(
            #'instruments_add_dialog_path', ''),
        )
        if not path:
            return

        project = EditorProject(self)
        project.create(path)

        self.addProject(project)


class EditorApp(BaseEditorApp):
    def __init__(self, process, runtime_settings, paths, settings=None):
        super().__init__(process, runtime_settings, settings)

        self.paths = paths

        self._old_excepthook = None
        self.win = None

    async def setup(self):
        logger.info("Installing custom excepthook.")
        self._old_excepthook = sys.excepthook
        sys.excepthook = ExceptHook(self)

        await super().setup()

        logger.info("Creating InstrumentLibrary.")
        self.instrument_library = None #InstrumentLibrary()

        logger.info("Creating EditorWindow.")
        self.win = EditorWindow(self)
        self.win.show()

        if self.paths:
            logger.info("Starting with projects from cmdline.")
            for path in self.paths:
                if path.startswith('+'):
                    path = path[1:]
                    await self.project_registry.create_project(path)
                else:
                    await self.project_registry.open_project(path)

        else:
            reopen_projects = self.settings.value('opened_projects', [])
            for path in reopen_projects or []:
                await self.project_registry.open_project(path)

        self.aboutToQuit.connect(self.shutDown)

    def shutDown(self):
        logger.info("Shutting down.")

        if self.win is not None:
            self.win.storeState()
            self.settings.sync()
            self.dumpSettings()

    async def cleanup(self):
        if self.win is not None:
            self.win.closeAll()
            self.win = None

        await super().cleanup()

        logger.info("Remove custom excepthook.")
        sys.excepthook = self._old_excepthook

    def createSequencer(self):
        # Do other clients handle non-ASCII names?
        # 'aconnect' seems to work (or just spits out whatever bytes it gets
        # and the console interprets it as UTF-8), 'aconnectgui' shows the
        # encoded bytes.
        return devices.AlsaSequencer('noisicaä')
