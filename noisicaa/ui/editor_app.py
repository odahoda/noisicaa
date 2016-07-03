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

from noisicaa import audioproc
from noisicaa import music
from noisicaa import devices
from ..exceptions import RestartAppException, RestartAppCleanException
from ..constants import EXIT_EXCEPTION, EXIT_RESTART, EXIT_RESTART_CLEAN
from .editor_window import EditorWindow

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


class AudioProcClientImpl(object):
    def __init__(self, event_loop, server):
        super().__init__()
        self.event_loop = event_loop
        self.server = server

    async def setup(self):
        pass

    async def cleanup(self):
        pass

class AudioProcClient(audioproc.AudioProcClientMixin, AudioProcClientImpl):
    pass


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
        self.audioproc_client = None
        self.audioproc_process = None

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

        self.show_edit_areas_action = QAction(
            "Show Edit Areas", self,
            checkable=True,
            triggered=self.onShowEditAreasChanged)
        self.show_edit_areas_action.setChecked(
            int(self.settings.value('dev/show_edit_areas', '0')))

        await self.createAudioProcProcess()

    async def cleanup(self):
        logger.info("Cleaning up.")

        if self.audioproc_client is not None:
            await self.audioproc_client.disconnect(shutdown=True)
            await self.audioproc_client.cleanup()
            self.audioproc_client = None

        if self.midi_hub is not None:
            self.midi_hub.stop()
            self.midi_hub = None

        if self.sequencer is not None:
            self.sequencer.close()
            self.sequencer = None

        if self.project_registry is not None:
            await self.project_registry.close_all()
            self.project_registry = None

    def quit(self, exit_code=0):
        self.process.quit(exit_code)

    def createSequencer(self):
        return None

    def createMidiHub(self):
        return devices.MidiHub(self.sequencer)

    async def createAudioProcProcess(self):
        pass

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

    async def createProject(self, path):
        project = await self.project_registry.create_project(path)
        await self.addProject(project)
        return project

    async def openProject(self, path):
        project = await self.project_registry.open_project(path)
        await self.addProject(project)
        return project

    def _updateOpenedProjects(self):
        self.settings.setValue(
            'opened_projects',
            sorted(
                project.path
                for project
                in self.project_registry.projects.values()
                if project.path))

    async def addProject(self, project_connection):
        self.win.addProjectView(project_connection)
        project_connection.playback_node = await self.audioproc_client.add_node(
            'ipc', address=project_connection.client.audiostream_address)
        await self.audioproc_client.connect_ports(
            project_connection.playback_node, 'out', 'sink', 'in')
        self._updateOpenedProjects()

    async def removeProject(self, project_connection):
        if project_connection.playback_node is not None:
            await self.audioproc_client.disconnect_ports(
                project_connection.playback_node, 'out', 'sink', 'in')
            await self.audioproc_client.remove_node(
                project_connection.playback_node)
            project_connection.playback_node = None

        self.win.removeProjectView(project_connection)
        self._updateOpenedProjects()
        await self.project_registry.close_project(project_connection)


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
                    project = await self.project_registry.create_project(
                        path)
                else:
                    project = await self.project_registry.open_project(
                        path)
                await self.addProject(project)
        else:
            reopen_projects = self.settings.value('opened_projects', [])
            for path in reopen_projects or []:
                project = await self.project_registry.open_project(path)
                await self.addProject(project)

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

    async def createAudioProcProcess(self):
        self.audioproc_process = await self.process.manager.call(
            'CREATE_AUDIOPROC_PROCESS', 'main')

        self.audioproc_client = AudioProcClient(
            self.process.event_loop, self.process.server)
        await self.audioproc_client.setup()
        await self.audioproc_client.connect(self.audioproc_process)

        await self.audioproc_client.set_backend(
            self.settings.value('audio/backend', 'pyaudio'))
