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

import logging
import typing
from typing import Any, Optional, Iterator, MutableSequence

from noisicaa.core.typing_extra import down_cast
from noisicaa import audioproc
from noisicaa import node_db
from noisicaa.music import graph
from noisicaa.music import commands
from noisicaa.builtin_nodes import commands_registry_pb2
from . import commands_pb2
from . import processor_pb2
from . import model

if typing.TYPE_CHECKING:
    from noisicaa import core

logger = logging.getLogger(__name__)


class UpdateCustomCSound(commands.Command):
    proto_type = 'update_custom_csound'
    proto_ext = commands_registry_pb2.update_custom_csound

    def run(self) -> None:
        pb = down_cast(commands_pb2.UpdateCustomCSound, self.pb)
        node = down_cast(CustomCSound, self.pool[pb.node_id])

        if pb.HasField('set_orchestra'):
            node.orchestra = pb.set_orchestra

        if pb.HasField('set_score'):
            node.score = pb.set_score


class CreateCustomCSoundPort(commands.Command):
    proto_type = 'create_custom_csound_port'
    proto_ext = commands_registry_pb2.create_custom_csound_port

    def validate(self) -> None:
        pb = down_cast(commands_pb2.CreateCustomCSoundPort, self.pb)

        if pb.node_id not in self.pool:
            raise ValueError("Unknown node %016x" % pb.node_id)

        node = down_cast(CustomCSound, self.pool[pb.node_id])

        if pb.HasField('index'):
            if not 0 <= pb.index <= len(node.ports):
                raise ValueError("index %d out of bounds [0, %d]" % (pb.index, len(node.ports)))

    def run(self) -> None:
        pb = down_cast(commands_pb2.CreateCustomCSoundPort, self.pb)
        node = down_cast(CustomCSound, self.pool[pb.node_id])

        if pb.HasField('index'):
            index = pb.index
        else:
            index = len(node.ports)

        port = self.pool.create(
            CustomCSoundPort,
            name=pb.name,
            csound_name='ga' + pb.name.capitalize(),
            type=node_db.PortDescription.AUDIO,
            direction=node_db.PortDescription.OUTPUT)
        node.ports.insert(index, port)


class UpdateCustomCSoundPort(commands.Command):
    proto_type = 'update_custom_csound_port'
    proto_ext = commands_registry_pb2.update_custom_csound_port

    def run(self) -> None:
        pb = down_cast(commands_pb2.UpdateCustomCSoundPort, self.pb)
        port = down_cast(CustomCSoundPort, self.pool[pb.port_id])

        if pb.HasField('set_csound_name'):
            port.csound_name = pb.set_csound_name


class DeleteCustomCSoundPort(commands.Command):
    proto_type = 'delete_custom_csound_port'
    proto_ext = commands_registry_pb2.delete_custom_csound_port

    def run(self) -> None:
        pb = down_cast(commands_pb2.DeleteCustomCSoundPort, self.pb)
        port = down_cast(CustomCSoundPort, self.pool[pb.port_id])
        node = down_cast(CustomCSound, port.parent)

        port.remove_connections()
        del node.ports[port.index]


class CustomCSoundPort(model.CustomCSoundPort, graph.Port):
    def create(
            self, *,
            csound_name: Optional[str] = None,
            **kwargs: Any
        ) -> None:
        super().create(**kwargs)

        self.csound_name = csound_name

    @property
    def node(self) -> 'CustomCSound':
        return down_cast(CustomCSound, self.parent)

    @property
    def csound_name(self) -> str:
        return self.get_property_value('csound_name')

    @csound_name.setter
    def csound_name(self, value: str) -> None:
        self.set_property_value('csound_name', value)


class CustomCSound(model.CustomCSound, graph.BaseNode):
    def create(
            self, *,
            orchestra: Optional[str] = None,
            score: Optional[str] = None,
            **kwargs: Any
        ) -> None:
        super().create(**kwargs)

        self.orchestra = orchestra
        self.score = score

    def setup(self) -> None:
        super().setup()
        self.orchestra_preamble_changed.add(lambda _: self.__code_changed())
        self.orchestra_changed.add(lambda _: self.__code_changed())
        self.score_changed.add(lambda _: self.__code_changed())

    def __get_code_mutation(self) -> audioproc.Mutation:
        params = audioproc.NodeParameters()
        csound_params = params.Extensions[processor_pb2.custom_csound_parameters]
        csound_params.orchestra = self.full_orchestra
        csound_params.score = self.score or ''
        return audioproc.Mutation(
            set_node_parameters=audioproc.SetNodeParameters(
                node_id=self.pipeline_node_id,
                parameters=params))

    def __code_changed(self) -> None:
        if self.attached_to_project:
            self.project.handle_pipeline_mutation(
                self.__get_code_mutation())

    def get_initial_parameter_mutations(self) -> Iterator[audioproc.Mutation]:
        yield from super().get_initial_parameter_mutations()
        yield self.__get_code_mutation()

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

    @property
    def ports(self) -> MutableSequence[CustomCSoundPort]:
        return self.get_property_value('ports')
