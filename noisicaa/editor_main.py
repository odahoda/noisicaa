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

import argparse
import asyncio
import functools
import signal
import sys
import time
from typing import Dict, List

from .constants import EXIT_SUCCESS, EXIT_RESTART, EXIT_RESTART_CLEAN
from .runtime_settings import RuntimeSettings
from .core import process_manager
from .core import init_pylogging
from .core import empty_message_pb2
from . import logging
from . import debug_console
from . import editor_main_pb2


class Editor(object):
    def __init__(
            self, runtime_settings: RuntimeSettings,
            paths: List[str],
            logger: logging.Logger,
            log_manager: logging.LogManager,
            enable_debug_console: bool,
    ) -> None:
        self.runtime_settings = runtime_settings
        self.paths = paths
        self.logger = logger
        self.log_manager = log_manager
        self.enable_debug_console = enable_debug_console

        self.event_loop = asyncio.get_event_loop()
        self.manager = process_manager.ProcessManager(self.event_loop)
        self.stop_event = asyncio.Event(loop=self.event_loop)
        self.returncode = 0

        self.node_db_process = None  # type: process_manager.ProcessHandle
        self.node_db_process_lock = asyncio.Lock(loop=self.event_loop)

        self.instrument_db_process = None  # type: process_manager.ProcessHandle
        self.instrument_db_process_lock = asyncio.Lock(loop=self.event_loop)

        self.urid_mapper_process = None  # type: process_manager.ProcessHandle
        self.urid_mapper_process_lock = asyncio.Lock(loop=self.event_loop)

        self.project_processes = {}  # type: Dict[str, process_manager.ProcessHandle]
        self.project_processes_lock = asyncio.Lock(loop=self.event_loop)

    def run(self) -> int:
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

    async def run_async(self) -> None:
        async with self.manager:
            dbg = None  # type: debug_console.DebugConsole
            if self.enable_debug_console:
                dbg = debug_console.DebugConsole(self.event_loop, self.manager, self.log_manager)
                await dbg.setup()

            try:
                self.manager.server['main'].add_handler(
                    'CREATE_PROJECT_PROCESS', self.handle_create_project_process,
                    editor_main_pb2.CreateProjectProcessRequest,
                    editor_main_pb2.CreateProcessResponse)
                self.manager.server['main'].add_handler(
                    'CREATE_AUDIOPROC_PROCESS', self.handle_create_audioproc_process,
                    editor_main_pb2.CreateAudioProcProcessRequest,
                    editor_main_pb2.CreateProcessResponse)
                self.manager.server['main'].add_handler(
                    'CREATE_NODE_DB_PROCESS', self.handle_create_node_db_process,
                    empty_message_pb2.EmptyMessage, editor_main_pb2.CreateProcessResponse)
                self.manager.server['main'].add_handler(
                    'CREATE_INSTRUMENT_DB_PROCESS', self.handle_create_instrument_db_process,
                    empty_message_pb2.EmptyMessage, editor_main_pb2.CreateProcessResponse)
                self.manager.server['main'].add_handler(
                    'CREATE_URID_MAPPER_PROCESS', self.handle_create_urid_mapper_process,
                    empty_message_pb2.EmptyMessage, editor_main_pb2.CreateProcessResponse)
                self.manager.server['main'].add_handler(
                    'CREATE_PLUGIN_HOST_PROCESS', self.handle_create_plugin_host_process,
                    empty_message_pb2.EmptyMessage, editor_main_pb2.CreateProcessResponse)
                self.manager.server['main'].add_handler(
                    'SHUTDOWN_PROCESS', self.handle_shutdown_process,
                    editor_main_pb2.ShutdownProcessRequest, empty_message_pb2.EmptyMessage)

                task = self.event_loop.create_task(self.launch_ui())
                task.add_done_callback(self.ui_closed)
                await self.stop_event.wait()
                self.logger.info("Shutting down...")

            finally:
                for project_process in self.project_processes.values():
                    await project_process.shutdown()

                if self.node_db_process is not None:
                    await self.node_db_process.shutdown()

                if self.instrument_db_process is not None:
                    await self.instrument_db_process.shutdown()

                if self.urid_mapper_process is not None:
                    await self.urid_mapper_process.shutdown()

                if dbg is not None:
                    await dbg.cleanup()

    def handle_signal(
            self,
            sig: signal.Signals  # pylint: disable=no-member
    ) -> None:
        self.logger.info("%s received.", sig.name)
        self.stop_event.set()

    async def launch_ui(self) -> int:
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

    def ui_closed(self, task: asyncio.Task) -> None:
        if task.exception():
            self.logger.error("UI failed with an exception: %s", task.exception())
            self.returncode = 1
        else:
            self.returncode = task.result()
        self.stop_event.set()

    async def handle_create_project_process(
            self,
            request: editor_main_pb2.CreateProjectProcessRequest,
            response: editor_main_pb2.CreateProcessResponse
    ) -> None:
        async with self.project_processes_lock:
            try:
                proc = self.project_processes[request.uri]
            except KeyError:
                proc = self.project_processes[request.uri] = await self.manager.start_subprocess(
                    'project', 'noisicaa.music.project_process.ProjectSubprocess')

        response.address = proc.address

    async def handle_create_audioproc_process(
            self,
            request: editor_main_pb2.CreateAudioProcProcessRequest,
            response: editor_main_pb2.CreateProcessResponse
    ) -> None:
        # TODO: keep map of name->proc, only create processes for new
        # names.
        proc = await self.manager.start_subprocess(
            'audioproc<%s>' % request.name,
            'noisicaa.audioproc.audioproc_process.AudioProcSubprocess',
            enable_rt_checker=True,
            block_size=(
                request.host_parameters.block_size
                if request.host_parameters.HasField('block_size')
                else None),
            sample_rate=(
                request.host_parameters.sample_rate
                if request.host_parameters.HasField('sample_rate')
                else None))
        response.address = proc.address

    async def handle_create_node_db_process(
            self,
            request: empty_message_pb2.EmptyMessage,
            response: editor_main_pb2.CreateProcessResponse
    ) -> None:
        async with self.node_db_process_lock:
            if self.node_db_process is None:
                self.node_db_process = await self.manager.start_subprocess(
                    'node_db',
                    'noisicaa.node_db.process.NodeDBSubprocess')

        response.address = self.node_db_process.address

    async def handle_create_instrument_db_process(
            self,
            request: empty_message_pb2.EmptyMessage,
            response: editor_main_pb2.CreateProcessResponse
    ) -> None:
        async with self.instrument_db_process_lock:
            if self.instrument_db_process is None:
                self.instrument_db_process = await self.manager.start_subprocess(
                    'instrument_db',
                    'noisicaa.instrument_db.process.InstrumentDBSubprocess')

        response.address = self.instrument_db_process.address

    async def handle_create_urid_mapper_process(
            self,
            request: empty_message_pb2.EmptyMessage,
            response: editor_main_pb2.CreateProcessResponse
    ) -> None:
        async with self.urid_mapper_process_lock:
            if self.urid_mapper_process is None:
                self.urid_mapper_process = await self.manager.start_subprocess(
                    'urid_mapper',
                    'noisicaa.lv2.urid_mapper_process.URIDMapperSubprocess')

        response.address = self.urid_mapper_process.address

    async def handle_create_plugin_host_process(
            self,
            request: empty_message_pb2.EmptyMessage,
            response: editor_main_pb2.CreateProcessResponse
    ) -> None:
        proc = await self.manager.start_subprocess(
            'plugin',
            'noisicaa.audioproc.engine.plugin_host_process.PluginHostSubprocess')
        response.address = proc.address

    async def handle_shutdown_process(
            self,
            request: editor_main_pb2.ShutdownProcessRequest,
            response: empty_message_pb2.EmptyMessage
    ) -> None:
        await self.manager.shutdown_process(request.address)

        async with self.project_processes_lock:
            for uri, proc in self.project_processes.items():
                if proc.address == request.address:
                    del self.project_processes[uri]
                    break


class Main(object):
    def __init__(self) -> None:
        self.action = None  # type: str
        self.enable_debug_console = False
        self.runtime_settings = RuntimeSettings()
        self.paths = []  # type: List[str]
        self.logger = None  # type: logging.Logger

    def run(self, argv: List[str]) -> int:
        self.parse_args(argv)

        with logging.LogManager(self.runtime_settings) as log_manager:
            self.logger = logging.getLogger(__name__)

            if self.action == 'editor':
                rc = Editor(
                    self.runtime_settings, self.paths, self.logger, log_manager,
                    self.enable_debug_console
                ).run()

            # elif self.action == 'pdb':
            #     from . import pdb
            #     rc = pdb.ProjectDebugger(self.runtime_settings, self.paths).run()

            else:
                raise ValueError(self.action)

        return rc

    def parse_args(self, argv: List[str]) -> None:
        parser = argparse.ArgumentParser(
            prog=argv[0])
        parser.add_argument(
            '--action',
            choices=['editor', 'pdb'],
            default='editor',
            help="Action to execute. editor: Open editor UI. pdb: Run project debugger.")
        parser.add_argument(
            '--debug-console',
            action='store_true',
            default=False,
            help="Enable the debug console.")
        parser.add_argument(
            'path',
            nargs='*',
            help="Project file to open.")
        self.runtime_settings.init_argparser(parser)
        args = parser.parse_args(args=argv[1:])
        self.runtime_settings.set_from_args(args)
        self.paths = args.path
        self.action = args.action
        self.enable_debug_console = args.debug_console

if __name__ == '__main__':
    sys.exit(Main().run(sys.argv))
