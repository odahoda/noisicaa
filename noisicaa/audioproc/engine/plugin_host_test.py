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

import contextlib

from noisidev import unittest_mixins
from noisidev import unittest_engine_mixins
from noisicaa import node_db
from . import plugin_host_pb2
from . import plugin_host


class PluginHostMixin(unittest_mixins.NodeDBMixin, unittest_engine_mixins.HostSystemMixin):
    @contextlib.contextmanager
    def setup_plugin(self, block_size, plugin_uri):
        spec = plugin_host_pb2.PluginInstanceSpec()
        spec.realm = 'root'
        spec.node_id = '1234'
        spec.node_description.CopyFrom(self.node_db[plugin_uri])

        plugin = plugin_host.PyPluginHost(spec, self.host_system)
        try:
            plugin.setup()

            bufp = {}
            for idx, port in enumerate(spec.node_description.ports):
                if port.type == node_db.PortDescription.AUDIO:
                    bufsize = block_size * 4
                    valuetype = 'f'
                elif port.type == node_db.PortDescription.KRATE_CONTROL:
                    bufsize = 4
                    valuetype = 'f'
                elif port.type == node_db.PortDescription.EVENTS:
                    bufsize = 10240
                    valuetype = 'B'
                else:
                    raise ValueError(port.type)

                buf = bytearray(bufsize)
                plugin.connect_port(idx, buf)

                # TODO: mypy doesn't know memoryview.cast
                bufp[port.name] = memoryview(buf).cast(valuetype)  # type: ignore

            yield plugin, bufp

        finally:
            plugin.cleanup()
