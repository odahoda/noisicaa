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
import typing
from typing import Any, Optional, Dict, Callable

from google.protobuf import message as protobuf

from noisicaa.core.typing_extra import down_cast
from noisicaa import audioproc
from noisicaa.music import pipeline_graph
from noisicaa.music import node_connector
from noisicaa.music import pmodel
from noisicaa.music import commands
from noisicaa.builtin_nodes import commands_registry_pb2
from . import commands_pb2
from . import processor_messages
from . import model

if typing.TYPE_CHECKING:
    from noisicaa import core

logger = logging.getLogger(__name__)


class UpdateCustomCSound(commands.Command):
    proto_type = 'update_custom_csound'
    proto_ext = commands_registry_pb2.update_custom_csound  # type: ignore

    def run(self, project: pmodel.Project, pool: pmodel.Pool, pb: protobuf.Message) -> None:
        pb = down_cast(commands_pb2.UpdateCustomCSound, pb)
        node = down_cast(CustomCSound, pool[self.proto.command.target])

        if pb.HasField('orchestra'):
            node.orchestra = pb.orchestra

        if pb.HasField('score'):
            node.score = pb.score

commands.Command.register_command(UpdateCustomCSound)


class Connector(node_connector.NodeConnector):
    _node = None  # type: CustomCSound

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.__node_id = self._node.pipeline_node_id
        self.__listeners = {}  # type: Dict[str, core.Listener]

    def _init_internal(self) -> None:
        self.__set_script(self._node.orchestra, self._node.score)

        self.__listeners['orchestra'] = self._node.orchestra_changed.add(
            lambda change: self.__set_script(change.new_value, self._node.score))
        self.__listeners['score'] = self._node.score_changed.add(
            lambda change: self.__set_script(self._node.orchestra, change.new_value))

    def close(self) -> None:
        for listener in self.__listeners.values():
            listener.remove()
        self.__listeners.clear()

        super().close()

    def __set_script(self, orchestra: str, score: str) -> None:
        self._emit_message(processor_messages.set_script(
            self.__node_id,
            orchestra=orchestra or '',
            score=score or ''))


class CustomCSound(model.CustomCSound, pipeline_graph.BasePipelineGraphNode):
    def create(
            self, *,
            orchestra: Optional[str] = None,
            score: Optional[str] = None,
            **kwargs: Any
        ) -> None:
        super().create(**kwargs)

        self.orchestra = orchestra
        self.score = score

    @property
    def orchestra(self) -> str:
        return self.get_property_value('orchestra')

    @orchestra.setter
    def orchestra(self, value: str) -> None:
        self.set_property_value('orchestra', value)

    @property
    def score(self) -> str:
        return self.get_property_value('score')

    @score.setter
    def score(self, value: str) -> None:
        self.set_property_value('score', value)

    def create_node_connector(
            self, message_cb: Callable[[audioproc.ProcessorMessage], None]
    ) -> Connector:
        return Connector(node=self, message_cb=message_cb)
