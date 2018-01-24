#!/usr/bin/python3

# @begin:license
#
# Copyright (c) 2015-2018, Benjamin Niemann <pink@odahoda.de>
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

# TODO: pylint-unclean

import logging
import os
import pprint
import sys
import traceback

from PyQt5 import QtCore
from PyQt5 import QtWidgets

from noisicaa import audioproc
from noisicaa import instrument_db
from noisicaa import node_db
from noisicaa import devices
from ..exceptions import RestartAppException, RestartAppCleanException
from ..constants import EXIT_EXCEPTION, EXIT_RESTART, EXIT_RESTART_CLEAN
from .editor_window import EditorWindow

from . import project_registry
from . import pipeline_perf_monitor
from . import stat_monitor
from . import ui_base

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
        self.app.crashWithMessage("Uncaught exception", msg)


class AudioProcClientImpl(object):
    def __init__(self, event_loop, server):
        super().__init__()
        self.event_loop = event_loop
        self.server = server

    async def setup(self):
        pass

    async def cleanup(self):
        pass

class AudioProcClient(
        audioproc.AudioProcClientMixin, AudioProcClientImpl):
    def __init__(self, app, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.__app = app

    def handle_pipeline_status(self, status):
        self.__app.onPipelineStatus(status)


class NodeDBClientImpl(object):
    def __init__(self, event_loop, server):
        super().__init__()
        self.event_loop = event_loop
        self.server = server

    async def setup(self):
        pass

    async def cleanup(self):
        pass

class NodeDBClient(node_db.NodeDBClientMixin, NodeDBClientImpl):
    pass


class InstrumentDBClientImpl(object):
    def __init__(self, event_loop, server):
        super().__init__()
        self.event_loop = event_loop
        self.server = server

    async def setup(self):
        pass

    async def cleanup(self):
        pass

class InstrumentDBClient(instrument_db.InstrumentDBClientMixin, InstrumentDBClientImpl):
    pass


class BaseEditorApp(object):
    def __init__(self, *, process, runtime_settings, settings=None):
        self.__context = ui_base.CommonContext(app=self)

        self.process = process

        self.runtime_settings = runtime_settings

        if settings is None:
            settings = QtCore.QSettings('odahoda.de', 'noisicaä')
            if runtime_settings.start_clean:
                settings.clear()
        self.settings = settings
        self.dumpSettings()

        self.project_registry = None
        self.sequencer = None
        self.midi_hub = None
        self.show_edit_areas_action = None
        self.audioproc_client = None
        self.audioproc_process = None
        self.node_db = None
        self.instrument_db = None

        self.__clipboard = None

    @property
    def context_args(self):
        return {'context': self.__context}

    async def setup(self):
        await self.createNodeDB()
        await self.createInstrumentDB()

        self.project_registry = project_registry.ProjectRegistry(
            self.process.event_loop, self.process.tmp_dir, self.process.manager, self.node_db)

        self.sequencer = self.createSequencer()

        self.midi_hub = self.createMidiHub()
        self.midi_hub.start()

        self.show_edit_areas_action = QtWidgets.QAction(
            "Show Edit Areas", self,
            checkable=True,
            triggered=self.onShowEditAreasChanged)
        self.show_edit_areas_action.setChecked(
            int(self.settings.value('dev/show_edit_areas', '0')))

        await self.createAudioProcProcess()

    async def cleanup(self):
        logger.info("Cleaning up.")

        if self.project_registry is not None:
            await self.project_registry.close_all()
            self.project_registry = None

        if self.audioproc_client is not None:
            await self.audioproc_client.disconnect(shutdown=True)
            await self.audioproc_client.cleanup()
            self.audioproc_client = None

        if self.instrument_db is not None:
            await self.instrument_db.disconnect(shutdown=True)
            await self.instrument_db.cleanup()
            self.instrument_db = None

        if self.node_db is not None:
            await self.node_db.disconnect(shutdown=True)
            await self.node_db.cleanup()
            self.node_db = None

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

    async def createAudioProcProcess(self):
        pass

    async def createNodeDB(self):
        node_db_address = await self.process.manager.call(
            'CREATE_NODE_DB_PROCESS')

        self.node_db = NodeDBClient(
            self.process.event_loop, self.process.server)
        await self.node_db.setup()
        await self.node_db.connect(node_db_address)

    async def createInstrumentDB(self):
        instrument_db_address = await self.process.manager.call(
            'CREATE_INSTRUMENT_DB_PROCESS')

        self.instrument_db = InstrumentDBClient(
            self.process.event_loop, self.process.server)
        await self.instrument_db.setup()
        await self.instrument_db.connect(instrument_db_address)

    def dumpSettings(self):
        for key in self.settings.allKeys():
            value = self.settings.value(key)
            if isinstance(value, (bytes, QtCore.QByteArray)):
                value = '[%d bytes]' % len(value)
            logger.info('%s: %s', key, value)

    def onShowEditAreasChanged(self):
        self.settings.setValue(
            'dev/show_edit_areas', int(self.show_edit_areas_action.isChecked()))

    @property
    def showEditAreas(self):
        return (self.runtime_settings.dev_mode
                and self.show_edit_areas_action.isChecked())

    async def createProject(self, path):
        project_connection = self.project_registry.add_project(path)
        idx = self.win.addProjectSetupView(project_connection)
        await project_connection.create()
        await self.win.activateProjectView(idx, project_connection)
        self._updateOpenedProjects()

    async def openProject(self, path):
        project_connection = self.project_registry.add_project(path)
        idx = self.win.addProjectSetupView(project_connection)
        await project_connection.open()
        await self.win.activateProjectView(idx, project_connection)
        self._updateOpenedProjects()

    def _updateOpenedProjects(self):
        self.settings.setValue(
            'opened_projects',
            sorted(
                project.path
                for project in self.project_registry.projects.values()
                if project.path))

    async def removeProject(self, project_connection):
        await self.win.removeProjectView(project_connection)
        await self.project_registry.close_project(project_connection)
        self._updateOpenedProjects()

    def onPipelineStatus(self, status):
        pass

    def setClipboardContent(self, content):
        logger.info(
            "Setting clipboard contents to: %s", pprint.pformat(content))
        self.__clipboard = content

    def clipboardContent(self):
        return self.__clipboard


class EditorApp(BaseEditorApp, QtWidgets.QApplication):
    def __init__(self, *, paths, **kwargs):
        QtWidgets.QApplication.__init__(self, ['noisicaä'])
        BaseEditorApp.__init__(self, **kwargs)

        self.paths = paths

        self._old_excepthook = None
        self.win = None
        self.pipeline_perf_monitor = None
        self.pipeline_graph_monitor = None
        self.stat_monitor = None
        self.default_style = None

        self.setQuitOnLastWindowClosed(False)

    async def setup(self):
        logger.info("Installing custom excepthook.")
        self._old_excepthook = sys.excepthook
        sys.excepthook = ExceptHook(self)

        await super().setup()

        self.default_style = self.style().objectName()

        style_name = self.settings.value('appearance/qtStyle', '')
        if style_name:
            style = QtWidgets.QStyleFactory.create(style_name)
            self.setStyle(style)

        logger.info("Creating PipelinePerfMonitor.")
        self.pipeline_perf_monitor = pipeline_perf_monitor.PipelinePerfMonitor(**self.context_args)

        # logger.info("Creating PipelineGraphMonitor.")
        # self.pipeline_graph_monitor = pipeline_graph_monitor.PipelineGraphMonitor(**self.context_args)

        logger.info("Creating StatMonitor.")
        self.stat_monitor = stat_monitor.StatMonitor(**self.context_args)

        logger.info("Creating EditorWindow.")
        self.win = EditorWindow(**self.context_args)
        await self.win.setup()
        self.win.show()

        # self.pipeline_graph_monitor.addWindow(self.win)

        if self.paths:
            logger.info("Starting with projects from cmdline.")
            for path in self.paths:
                if path.startswith('+'):
                    await self.createProject(path[1:])
                else:
                    await self.openProject(path)
        else:
            reopen_projects = self.settings.value('opened_projects', [])
            for path in reopen_projects or []:
                await self.openProject(path)

    async def cleanup(self):
        logger.info("Cleanup app...")

        if self.stat_monitor is not None:
            self.stat_monitor.storeState()
            self.stat_monitor = None

        if self.pipeline_perf_monitor is not None:
            self.pipeline_perf_monitor.storeState()
            self.pipeline_perf_monitor = None

        if self.pipeline_graph_monitor is not None:
            self.pipeline_graph_monitor.storeState()
            self.pipeline_graph_monitor = None

        if self.win is not None:
            self.win.storeState()
            await self.win.cleanup()
            self.win = None

        self.settings.sync()
        self.dumpSettings()

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
            self, self.process.event_loop, self.process.server)
        await self.audioproc_client.setup()
        await self.audioproc_client.connect(
            self.audioproc_process, {'perf_data'})

        await self.audioproc_client.set_backend(
            self.settings.value('audio/backend', 'portaudio'),
            block_size=2 ** int(self.settings.value('audio/block_size', 10)))

    def onPipelineStatus(self, status):
        if 'perf_data' in status:
            if self.pipeline_perf_monitor is not None:
                self.pipeline_perf_monitor.addPerfData(
                    status['perf_data'])

    def crashWithMessage(self, title, msg):
        logger.error('%s: %s', title, msg)

        try:
            errorbox = QtWidgets.QMessageBox()
            errorbox.setWindowTitle("noisicaä crashed")
            errorbox.setText(title)
            errorbox.setInformativeText(msg)
            errorbox.setIcon(QtWidgets.QMessageBox.Critical)
            errorbox.addButton("Exit", QtWidgets.QMessageBox.AcceptRole)
            errorbox.exec_()
        except:
            logger.error(
                "Failed to show crash dialog: %s", traceback.format_exc())

        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(EXIT_EXCEPTION)
