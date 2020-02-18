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
import concurrent.futures
import functools
import logging
import os
import threading
import traceback
import typing
from typing import Any, Dict, Tuple
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
from noisicaa.core import empty_message_pb2
from noisicaa.core import ipc
from noisicaa import lv2
from noisicaa import host_system as host_system_lib
from noisicaa import node_db
from noisicaa import editor_main_pb2
from noisicaa.audioproc import audioproc_pb2
from noisicaa.audioproc.public import control_value_pb2
from noisicaa.audioproc.public import plugin_state_pb2
from . import plugin_host_pb2
from . import plugin_host

if typing.TYPE_CHECKING:
    from . import plugin_ui_host

logger = logging.getLogger(__name__)


# TODO: this should not extend PyPluginHost, but be a proxy class.
class PluginHost(plugin_host.PyPluginHost):
    def __init__(
            self, *,
            spec: plugin_host_pb2.PluginInstanceSpec,
            callback_address: str = None,
            event_loop: asyncio.AbstractEventLoop,
            host_system: host_system_lib.HostSystem,
            tmp_dir: str) -> None:
        super().__init__(spec, host_system)

        self.__event_loop = event_loop
        self.__tmp_dir = tmp_dir
        self.__realm = spec.realm
        self.__spec = spec
        self.__node_id = spec.node_id
        self.__description = spec.node_description
        self.__callback_address = callback_address

        self.__callback_stub = None  # type: ipc.Stub
        self.__state = None  # type: plugin_state_pb2.PluginState
        self.__thread = None  # type: threading.Thread
        self.__thread_result = None  # type: concurrent.futures.Future
        self.__state_fetcher_task = None  # type: asyncio.Task
        self.__pipe_path = None  # type: str
        self.__pipe_fd = None  # type: int

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

    @property
    def callback_stub(self) -> ipc.Stub:
        assert self.__callback_stub is not None
        return self.__callback_stub

    def set_state(self, state: plugin_state_pb2.PluginState) -> None:
        super().set_state(state)
        self.__state = state

    # Parent class doesn't use async setup/cleanup.
    async def setup(self) -> None:  # type: ignore[override]
        super().setup()

        if self.__callback_address is not None:
            self.__callback_stub = ipc.Stub(self.__event_loop, self.__callback_address)
            await self.__callback_stub.connect()

        self.__pipe_path = os.path.join(
            self.__tmp_dir,
            'plugin-%s.%s.pipe' % (self.node_id, uuid.uuid4().hex))
        os.mkfifo(self.__pipe_path)
        self.__pipe_fd = os.open(self.__pipe_path, os.O_RDONLY | os.O_NONBLOCK)
        logger.info("Reading from %s...", self.__pipe_path)

        self.__thread_result = concurrent.futures.Future()
        self.__thread = threading.Thread(target=self.__main)
        self.__thread.start()

        if self.has_state():
            self.__state = plugin_state_pb2.PluginState()
            if self.__spec.initial_state is not None:
                self.__state.CopyFrom(self.__spec.initial_state)
            self.__state_fetcher_task = self.__event_loop.create_task(
                self.__state_fetcher_main())

    async def cleanup(self) -> None:  # type: ignore[override]
        if self.__state_fetcher_task:
            if not self.__state_fetcher_task.done():
                self.__state_fetcher_task.cancel()
            try:
                await self.__state_fetcher_task
            except asyncio.CancelledError:
                pass
            self.__state_fetcher_task = None

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

        if self.__callback_stub is not None:
            await self.__callback_stub.close()
            self.__callback_stub = None

        super().cleanup()

    def __main(self) -> None:
        try:
            with core.RTSafeLogging():
                self.main_loop(self.__pipe_fd)
        except core.ConnectionClosed as exc:
            logger.warning("Plugin pipe %s closed: %s", self.__pipe_path, exc)
            self.__thread_result.set_result(False)
        except Exception as exc:  # pylint: disable=broad-except
            self.__thread_result.set_exception(exc)
        else:
            self.__thread_result.set_result(True)

    async def __state_fetcher_main(self) -> None:
        try:
            while True:
                await asyncio.sleep(1.0, loop=self.__event_loop)

                state = self.get_state()
                if state != self.__state:
                    self.__state = state
                    logger.info("Plugin state for %s changed:\n%s", self.__node_id, self.__state)
                    await asyncio.shield(
                        self.__callback_stub.call(
                            'PLUGIN_STATE_CHANGE',
                            audioproc_pb2.PluginStateChange(
                                realm=self.__realm, node_id=self.__node_id, state=self.__state)),
                        loop=self.__event_loop)

        except asyncio.CancelledError:
            pass

        except:  # pylint: disable=bare-except
            logger.error("Exception in state fetcher:\n%s", traceback.format_exc())


class PluginHostProcess(core.ProcessBase):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.__urid_mapper = None  # type: lv2.ProxyURIDMapper
        self.__host_system = None  # type: host_system_lib.HostSystem

        self.__plugins = {}  # type: Dict[Tuple[str, str], PluginHost]
        self.__uis = {}  # type: Dict[Tuple[str, str], plugin_ui_host.PyPluginUIHost]

    async def setup(self) -> None:
        await super().setup()

        endpoint = ipc.ServerEndpoint('main')
        endpoint.add_handler(
            'CREATE_PLUGIN', self.__handle_create_plugin,
            plugin_host_pb2.CreatePluginRequest, plugin_host_pb2.CreatePluginResponse)
        endpoint.add_handler(
            'DELETE_PLUGIN', self.__handle_delete_plugin,
            plugin_host_pb2.DeletePluginRequest, empty_message_pb2.EmptyMessage)
        endpoint.add_handler(
            'CREATE_UI', self.__handle_create_ui,
            plugin_host_pb2.CreatePluginUIRequest, plugin_host_pb2.CreatePluginUIResponse)
        endpoint.add_handler(
            'DELETE_UI', self.__handle_delete_ui,
            plugin_host_pb2.DeletePluginUIRequest, empty_message_pb2.EmptyMessage)
        endpoint.add_handler(
            'SET_PLUGIN_STATE', self.__handle_set_plugin_state,
            plugin_host_pb2.SetPluginStateRequest, empty_message_pb2.EmptyMessage)
        await self.server.add_endpoint(endpoint)

        logger.info("Setting up URID mapper...")
        create_urid_mapper_response = editor_main_pb2.CreateProcessResponse()
        await self.manager.call(
            'CREATE_URID_MAPPER_PROCESS', None, create_urid_mapper_response)
        urid_mapper_address = create_urid_mapper_response.address

        self.__urid_mapper = lv2.ProxyURIDMapper(
            server_address=urid_mapper_address,
            tmp_dir=self.tmp_dir)
        await self.__urid_mapper.setup(self.event_loop)

        logger.info("Setting up host system...")
        self.__host_system = host_system_lib.HostSystem(self.__urid_mapper)
        self.__host_system.setup()

        logger.info("PluginHostProcess.setup() complete.")

    async def cleanup(self) -> None:
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

        await super().cleanup()

    async def __handle_create_plugin(
            self,
            request: plugin_host_pb2.CreatePluginRequest,
            response: plugin_host_pb2.CreatePluginResponse
    ) -> None:
        key = (request.spec.realm, request.spec.node_id)
        assert key not in self.__plugins

        plugin = PluginHost(
            spec=request.spec,
            callback_address=(
                request.callback_address if request.HasField('callback_address') else None),
            event_loop=self.event_loop,
            host_system=self.__host_system,
            tmp_dir=self.tmp_dir)
        await plugin.setup()

        self.__plugins[key] = plugin

        response.pipe_path = plugin.pipe_path

    async def __handle_delete_plugin(
            self,
            request: plugin_host_pb2.DeletePluginRequest,
            response: empty_message_pb2.EmptyMessage
    ) -> None:
        key = (request.realm, request.node_id)
        assert key in self.__plugins

        ui_host = self.__uis.pop(key, None)
        if ui_host is not None:
            ui_host.cleanup()

        plugin = self.__plugins.pop(key)
        await plugin.cleanup()

    async def __handle_create_ui(
            self,
            request: plugin_host_pb2.CreatePluginUIRequest,
            response: plugin_host_pb2.CreatePluginUIResponse
    ) -> None:
        key = (request.realm, request.node_id)
        assert key not in self.__uis

        plugin = self.__plugins[key]
        logger.info("Creating UI for plugin %s", plugin)

        ui_host = plugin.create_ui(
            functools.partial(self.__control_value_change, plugin))
        ui_host.setup()

        self.__uis[key] = ui_host

        response.wid = ui_host.wid
        response.width = ui_host.size[0]
        response.height = ui_host.size[1]

    async def __handle_delete_ui(
            self,
            request: plugin_host_pb2.DeletePluginUIRequest,
            response: empty_message_pb2.EmptyMessage
    ) -> None:
        key = (request.realm, request.node_id)
        ui_host = self.__uis.pop(key)
        ui_host.cleanup()

    async def __handle_set_plugin_state(
            self,
            request: plugin_host_pb2.SetPluginStateRequest,
            response: empty_message_pb2.EmptyMessage
    ) -> None:
        key = (request.realm, request.node_id)
        plugin = self.__plugins[key]
        plugin.set_state(request.state)

    def __control_value_change(
            self, plugin: PluginHost, port_index: int, value: float, generation: int
    ) -> None:
        port_desc = plugin.node_description.ports[port_index]
        task = asyncio.run_coroutine_threadsafe(
            plugin.callback_stub.call(
                'CONTROL_VALUE_CHANGE',
                audioproc_pb2.ControlValueChange(
                    realm=plugin.realm,
                    node_id=plugin.node_id,
                    value=control_value_pb2.ControlValue(
                        name=port_desc.name,
                        value=value,
                        generation=generation))),
            loop=self.event_loop)
        task.add_done_callback(self.__control_value_change_done)

    def __control_value_change_done(self, task: concurrent.futures.Future) -> None:
        try:
            task.result()
        except:  # pylint: disable=bare-except
            logger.error("Exception in CONTROL_VALUE_CHANGE call:\n%s", traceback.format_exc())


class PluginHostSubprocess(core.SubprocessMixin, PluginHostProcess):
    def create_event_loop(self) -> asyncio.AbstractEventLoop:
        gbulb.install(gtk=True)
        event_loop = asyncio.new_event_loop()
        return event_loop
