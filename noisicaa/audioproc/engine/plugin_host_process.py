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

# TODO: mypy-unclean

import asyncio
import concurrent.futures
import functools
import logging
import os
import threading
import typing
import uuid
import warnings

import gbulb
import gi
with warnings.catch_warnings():
    # gi warns that Gtk2 is not really compatible with PyGObject. Our use of it is very
    # minimal, and getting PyGTK into the virtualenv (as recommended) is a PITA (needs manual
    # build, no pip version available).
    # So let's cross fingers that is keeps working and suppress that warning.
    warnings.filterwarnings('ignore', r"You have imported the Gtk 2\.0 module")
    gi.require_version("Gtk", "2.0")
    from gi.repository import Gtk  # pylint: disable=unused-import

from noisicaa import core
from noisicaa import audioproc
from noisicaa import lv2
from noisicaa import host_system as host_system_lib
from noisicaa import node_db
from . import plugin_host_pb2
from . import plugin_host

logger = logging.getLogger(__name__)


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


class PluginHost(plugin_host.PyPluginHost):
    def __init__(
            self, *,
            spec: plugin_host_pb2.PluginInstanceSpec,
            host_system: host_system_lib.HostSystem,
            tmp_dir: str):
        super().__init__(spec, host_system)

        self.__tmp_dir = tmp_dir
        self.__realm = spec.realm
        self.__node_id = spec.node_id
        self.__description = spec.node_description

        self.__thread = None
        self.__thread_result = None
        self.__pipe_path = None
        self.__pipe_fd = None

    @property
    def realm(self) -> str:
        return self.__realm

    @property
    def node_id(self) -> str:
        return self.__node_id

    @property
    def node_description(self) -> node_db.NodeDescription:
        return self.__description

    @property
    def pipe_path(self) -> str:
        return self.__pipe_path

    async def setup(self) -> None:
        super().setup()

        self.__pipe_path = os.path.join(
            self.__tmp_dir,
            'plugin-%s.%s.pipe' % (self.node_id, uuid.uuid4().hex))
        os.mkfifo(self.__pipe_path)
        self.__pipe_fd = os.open(self.__pipe_path, os.O_RDONLY | os.O_NONBLOCK)
        logger.info("Reading from %s...", self.__pipe_path)

        self.__thread_result = concurrent.futures.Future()
        self.__thread = threading.Thread(target=self.__main)
        self.__thread.start()

    async def cleanup(self) -> None:
        if self.__thread is not None:
            self.exit_loop()
            self.__thread_result.result()
            self.__thread.join()
            self.__thread = None

        if self.__pipe_fd is not None:
            os.close(self.__pipe_fd)
            self.__pipe_fd = None

        if self.__pipe_path is not None:
            if os.path.exists(self.__pipe_path):
                os.unlink(self.__pipe_path)
            self.__pipe_path = None

        super().cleanup()

    def __main(self) -> None:
        try:
            self.main_loop(self.__pipe_fd)
        except core.ConnectionClosed as exc:
            logger.warning("Plugin pipe %s closed: %s", self.__pipe_path, exc)
            self.__thread_result.set_result(False)
        except Exception as exc:  # pylint: disable=broad-except
            self.__thread_result.set_exception(exc)
        else:
            self.__thread_result.set_result(True)


class PluginHostProcess(core.ProcessBase):
    def __init__(self, *, audioproc_address, **kwargs):
        super().__init__(**kwargs)

        self.__audioproc_address = audioproc_address

        self.__audioproc_client = None
        self.__audioproc_ping_task = None

        self.__urid_mapper = None
        self.__host_system = None

        self.__plugins = {}
        self.__uis = {}

    async def setup(self) -> None:
        await super().setup()

        self.server.add_command_handler('SHUTDOWN', self.shutdown)
        self.server.add_command_handler('CREATE_PLUGIN', self.__handle_create_plugin)
        self.server.add_command_handler('CREATE_UI', self.__handle_create_ui)
        self.server.add_command_handler('DELETE_UI', self.__handle_delete_ui)
        self.server.add_command_handler('DELETE_PLUGIN', self.__handle_delete_plugin)

        logger.info("Setting up audioproc client...")
        self.__audioproc_client = AudioProcClient(self.event_loop, self.server)
        await self.__audioproc_client.setup()
        await self.__audioproc_client.connect(self.__audioproc_address)

        #self.__audioproc_ping_task = self.event_loop.create_task(self.__audioproc_ping_main())

        logger.info("Setting up URID mapper...")
        urid_mapper_address = await self.manager.call('CREATE_URID_MAPPER_PROCESS')

        self.__urid_mapper = lv2.ProxyURIDMapper(
            server_address=urid_mapper_address,
            tmp_dir=self.tmp_dir)
        await self.__urid_mapper.setup(self.event_loop)

        logger.info("Setting up host system...")
        self.__host_system = host_system_lib.HostSystem(self.__urid_mapper)
        self.__host_system.setup()

        logger.info("PluginHostProcess.setup() complete.")

    async def cleanup(self) -> None:
        if self.__audioproc_ping_task is not None:
            self.__audioproc_ping_task.cancel()
            self.__audioproc_ping_task = None

        while self.__plugins:
            _, plugin = self.__plugins.popitem()
            await plugin.cleanup()

        if self.__host_system is not None:
            logger.info("Cleaning up host system...")
            self.__host_system.cleanup()
            self.__host_system = None

        if self.__urid_mapper is not None:
            logger.info("Cleaning up URID mapper...")
            await self.__urid_mapper.cleanup(self.event_loop)
            self.__urid_mapper = None

        if self.__audioproc_client is not None:
            logger.info("Cleaning up audioproc client...")
            await self.__audioproc_client.cleanup()
            self.__audioproc_client = None

        await super().cleanup()

    async def __audioproc_ping_main(self) -> None:
        while True:
            try:
                # TODO: doesn't fail, just hangs when audioproc server goes away...
                await self.__audioproc_client.ping()
            except Exception as exc:  # pylint: disable=broad-except
                logger.error("Failed to ping audioproc process: %s", exc)
                self.event_loop.create_task(self.shutdown())
                break

            await asyncio.sleep(1, loop=self.event_loop)

    async def __handle_create_plugin(self, spec: plugin_host_pb2.PluginInstanceSpec) -> str:
        key = (spec.realm, spec.node_id)
        assert key not in self.__plugins

        plugin = PluginHost(
            spec=spec,
            host_system=self.__host_system,
            tmp_dir=self.tmp_dir)
        await plugin.setup()

        self.__plugins[key] = plugin

        return plugin.pipe_path

    async def __handle_delete_plugin(self, realm: str, node_id: str) -> None:
        key = (realm, node_id)
        assert key in self.__plugins

        ui_host = self.__uis.pop(key, None)
        if ui_host is not None:
            ui_host.cleanup()

        plugin = self.__plugins.pop(key)
        await plugin.cleanup()

    async def __handle_create_ui(
            self, realm: str, node_id: str) -> typing.Tuple[int, typing.Tuple[int, int]]:
        key = (realm, node_id)
        assert key not in self.__uis

        plugin = self.__plugins[key]
        logger.info("Creating UI for plugin %s", plugin)

        ui_host = lv2.LV2UIHost(
            plugin.node_description, self.__host_system,
            functools.partial(self.__control_value_change, plugin))
        ui_host.setup()

        self.__uis[key] = ui_host

        return (ui_host.wid, ui_host.size)

    async def __handle_delete_ui(self, realm: str, node_id: str) -> None:
        key = (realm, node_id)
        ui_host = self.__uis.pop(key)
        ui_host.cleanup()

    def __control_value_change(self, plugin, port_index, value):
        port_desc = plugin.node_description.ports[port_index]
        task = asyncio.run_coroutine_threadsafe(
            self.__audioproc_client.set_control_value(
                plugin.realm, '%s:%s' % (plugin.node_id, port_desc.name), value),
            loop=self.event_loop)
        task.add_done_callback(self.__control_value_change_done)

    def __control_value_change_done(self, task):
        task.result()


class PluginHostSubprocess(core.SubprocessMixin, PluginHostProcess):
    def create_event_loop(self):
        gbulb.install(gtk=True)
        event_loop = asyncio.new_event_loop()
        return event_loop
