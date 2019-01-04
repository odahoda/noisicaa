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

import logging
import urllib.parse
import typing
from typing import Any, Optional, Iterator, List, Dict, Callable

from google.protobuf import message as protobuf

from noisicaa.core.typing_extra import down_cast
from noisicaa import audioproc
from . import pmodel
from . import pipeline_graph
from . import node_connector
from . import commands
from . import commands_pb2

if typing.TYPE_CHECKING:
    from noisicaa import core

logger = logging.getLogger(__name__)


class UpdateInstrument(commands.Command):
    proto_type = 'update_instrument'

    def run(self, project: pmodel.Project, pool: pmodel.Pool, pb: protobuf.Message) -> None:
        pb = down_cast(commands_pb2.UpdateInstrument, pb)
        node = down_cast(pmodel.Instrument, pool[self.proto.command.target])

        if pb.HasField('instrument_uri'):
            node.instrument_uri = pb.instrument_uri

commands.Command.register_command(UpdateInstrument)


class InvalidInstrumentURI(Exception):
    pass


class InstrumentConnector(node_connector.NodeConnector):
    _node = None  # type: Instrument

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.__node_id = self._node.pipeline_node_id
        self.__listeners = {}  # type: Dict[str, core.Listener]

    def _init_internal(self) -> None:
        self.__change_instrument(self._node.instrument_uri)

        self.__listeners['instrument_uri'] = self._node.instrument_uri_changed.add(
            lambda change: self.__change_instrument(change.new_value))

    def close(self) -> None:
        for listener in self.__listeners.values():
            listener.remove()
        self.__listeners.clear()

        super().close()

    def __change_instrument(self, instrument_uri: str) -> None:
        try:
            fmt, _, path, _, query, _ = urllib.parse.urlparse(instrument_uri)
            path = urllib.parse.unquote(path)
            if path == '':
                raise InvalidInstrumentURI("Missing path")

            if query:
                args = dict(urllib.parse.parse_qsl(query, strict_parsing=True))
            else:
                args = {}

            if fmt == 'sf2':
                instrument_spec = audioproc.InstrumentSpec(
                    sf2=audioproc.SF2InstrumentSpec(
                        path=path,
                        bank=int(args.get('bank', 0)),
                        preset=int(args.get('preset', 0))))

            elif fmt == 'sample':
                instrument_spec = audioproc.InstrumentSpec(
                    sample=audioproc.SampleInstrumentSpec(
                        path=path))

            else:
                raise InvalidInstrumentURI("Unknown scheme '%s'" % fmt)

            self._emit_message(
                audioproc.ProcessorMessage(
                    node_id=self.__node_id,
                    change_instrument=audioproc.ProcessorMessage.ChangeInstrument(
                        instrument_spec=instrument_spec)))

        except InvalidInstrumentURI as exc:
            logger.error("Invalid instrument URI '%s': %s", instrument_uri, exc)


class Instrument(pmodel.Instrument, pipeline_graph.BasePipelineGraphNode):
    def create(self, *, instrument_uri: Optional[str] = None, **kwargs: Any) -> None:
        super().create(**kwargs)

        self.instrument_uri = instrument_uri

    def create_node_connector(
            self, message_cb: Callable[[audioproc.ProcessorMessage], None]
    ) -> InstrumentConnector:
        return InstrumentConnector(node=self, message_cb=message_cb)

    def get_update_mutations(self) -> Iterator[audioproc.Mutation]:
        connections = []  # type: List[pmodel.PipelineGraphConnection]
        for connection in self.project.pipeline_graph_connections:
            if connection.source_node is self or connection.dest_node is self:
                connections.append(connection)

        for connection in connections:
            yield from connection.get_remove_mutations()
        yield from self.get_remove_mutations()
        yield from self.get_add_mutations()
        for connection in connections:
            yield from connection.get_add_mutations()

    def get_add_mutations(self) -> Iterator[audioproc.Mutation]:
        yield audioproc.AddNode(
            description=self.description,
            id=self.pipeline_node_id,
            name=self.name)

        yield from self.get_initial_parameter_mutations()

    def get_remove_mutations(self) -> Iterator[audioproc.Mutation]:
        yield audioproc.RemoveNode(self.pipeline_node_id)
