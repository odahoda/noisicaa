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

import argparse
import asyncio
import functools
import signal
import sys
import time

from .constants import EXIT_SUCCESS, EXIT_RESTART, EXIT_RESTART_CLEAN
from .runtime_settings import RuntimeSettings
from . import logging
from .core import process_manager, init_pylogging


class Editor(object):
    def __init__(self, runtime_settings, paths, logger):
        self.runtime_settings = runtime_settings
        self.paths = paths
        self.logger = logger

        self.event_loop = asyncio.get_event_loop()
        self.manager = process_manager.ProcessManager(self.event_loop)
        self.stop_event = asyncio.Event(loop=self.event_loop)
        self.returncode = 0

        self.node_db_process = None
        self.node_db_process_lock = asyncio.Lock(loop=self.event_loop)

        self.instrument_db_process = None
        self.instrument_db_process_lock = asyncio.Lock(loop=self.event_loop)

        self.urid_mapper_process = None
        self.urid_mapper_process_lock = asyncio.Lock(loop=self.event_loop)

    def run(self):
        for sig in (signal.SIGINT, signal.SIGTERM):
            self.event_loop.add_signal_handler(
                sig, functools.partial(self.handle_signal, sig))

        init_pylogging()

        try:
            self.event_loop.run_until_complete(self.run_async())
        finally:
            self.event_loop.stop()
            self.event_loop.close()

        return self.returncode

    async def run_async(self):
        async with self.manager:
            self.manager.server.add_command_handler(
                'CREATE_PROJECT_PROCESS', self.handle_create_project_process)
            self.manager.server.add_command_handler(
                'CREATE_AUDIOPROC_PROCESS',
                self.handle_create_audioproc_process)
            self.manager.server.add_command_handler(
                'CREATE_NODE_DB_PROCESS',
                self.handle_create_node_db_process)
            self.manager.server.add_command_handler(
                'CREATE_INSTRUMENT_DB_PROCESS',
                self.handle_create_instrument_db_process)
            self.manager.server.add_command_handler(
                'CREATE_URID_MAPPER_PROCESS',
                self.handle_create_urid_mapper_process)
            self.manager.server.add_command_handler(
                'CREATE_PLUGIN_HOST_PROCESS',
                self.handle_create_plugin_host_process)

            task = self.event_loop.create_task(self.launch_ui())
            task.add_done_callback(self.ui_closed)
            await self.stop_event.wait()
            self.logger.info("Shutting down...")

    def handle_signal(self, sig):
        self.logger.info("%s received.", sig.name)
        self.stop_event.set()

    async def launch_ui(self):
        while True:
            next_retry = time.time() + 5
            proc = await self.manager.start_subprocess(
                'ui', 'noisicaa.ui.ui_process.UISubprocess',
                runtime_settings=self.runtime_settings,
                paths=self.paths)
            await proc.wait()

            if proc.returncode == EXIT_RESTART:
                self.runtime_settings.start_clean = False

            elif proc.returncode == EXIT_RESTART_CLEAN:
                self.runtime_settings.start_clean = True

            elif proc.returncode == EXIT_SUCCESS:
                return proc.returncode

            else:
                self.logger.error(
                    "UI Process terminated with exit code %d",
                    proc.returncode)
                if self.runtime_settings.restart_on_crash:
                    self.runtime_settings.start_clean = False

                    delay = next_retry - time.time()
                    if delay > 0:
                        self.logger.warning(
                            "Sleeping %.1fsec before restarting.",
                            delay)
                        await asyncio.sleep(delay, loop=self.event_loop)
                else:
                    return proc.returncode

    def ui_closed(self, task):
        if task.exception():
            self.logger.error("UI failed with an exception: %s", task.exception())
            self.returncode = 1
        else:
            self.returncode = task.result()
        self.stop_event.set()

    async def handle_create_project_process(self, uri):
        # TODO: keep map of uri->proc, only create processes for new
        # URIs.
        proc = await self.manager.start_subprocess(
            'project', 'noisicaa.music.project_process.ProjectSubprocess')
        return proc.address

    async def handle_create_audioproc_process(self, name, **kwargs):
        # TODO: keep map of name->proc, only create processes for new
        # names.
        proc = await self.manager.start_subprocess(
            'audioproc<%s>' % name,
            'noisicaa.audioproc.audioproc_process.AudioProcSubprocess',
            **kwargs)
        return proc.address

    async def handle_create_node_db_process(self):
        async with self.node_db_process_lock:
            if self.node_db_process is None:
                self.node_db_process = await self.manager.start_subprocess(
                    'node_db',
                    'noisicaa.node_db.process.NodeDBSubprocess')

        return self.node_db_process.address

    async def handle_create_instrument_db_process(self):
        async with self.instrument_db_process_lock:
            if self.instrument_db_process is None:
                self.instrument_db_process = await self.manager.start_subprocess(
                    'instrument_db',
                    'noisicaa.instrument_db.process.InstrumentDBSubprocess')

        return self.instrument_db_process.address

    async def handle_create_urid_mapper_process(self):
        async with self.urid_mapper_process_lock:
            if self.urid_mapper_process is None:
                self.urid_mapper_process = await self.manager.start_subprocess(
                    'urid_mapper',
                    'noisicaa.lv2.urid_mapper_process.URIDMapperSubprocess')

        return self.urid_mapper_process.address

    async def handle_create_plugin_host_process(self, **kwargs):
        proc = await self.manager.start_subprocess(
            'plugin',
            'noisicaa.audioproc.engine.plugin_host_process.PluginHostSubprocess',
            **kwargs)
        return proc.address


class Main(object):
    def __init__(self):
        self.action = None
        self.runtime_settings = RuntimeSettings()
        self.paths = []
        self.logger = None

    def run(self, argv):
        self.parse_args(argv)

        with logging.LogManager(self.runtime_settings):
            self.logger = logging.getLogger(__name__)

            if self.action == 'editor':
                rc = Editor(self.runtime_settings, self.paths, self.logger).run()

            elif self.action == 'pdb':
                from . import pdb
                rc = pdb.ProjectDebugger(self.runtime_settings, self.paths).run()

            else:
                raise ValueError(self.action)

        return rc

    def parse_args(self, argv):
        parser = argparse.ArgumentParser(
            prog=argv[0])
        parser.add_argument(
            '--action',
            choices=['editor', 'pdb'],
            default='editor',
            help="Action to execute. editor: Open editor UI. pdb: Run project debugger.")
        parser.add_argument(
            'path',
            nargs='*',
            help="Project file to open.")
        self.runtime_settings.init_argparser(parser)
        args = parser.parse_args(args=argv[1:])
        self.runtime_settings.set_from_args(args)
        self.paths = args.path
        self.action = args.action


if __name__ == '__main__':
    sys.exit(Main().run(sys.argv))
