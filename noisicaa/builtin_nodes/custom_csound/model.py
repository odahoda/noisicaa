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
from typing import Any, Optional, Iterator

from noisicaa.core.typing_extra import down_cast
from noisicaa import core
from noisicaa import node_db
from noisicaa import audioproc
from noisicaa import music
from . import node_description
from . import processor_pb2
from . import _model

logger = logging.getLogger(__name__)


class CustomCSoundPort(_model.CustomCSoundPort):
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

    def csound_name_prefix(self, *, type: int = None) -> str:  # pylint: disable=redefined-builtin
        if type is None:
            type = self.type

        if type == node_db.PortDescription.KRATE_CONTROL:
            return 'gk'
        elif type in (node_db.PortDescription.ARATE_CONTROL,
                      node_db.PortDescription.AUDIO):
            return 'ga'
        else:
            assert type == node_db.PortDescription.EVENTS
            return ''

    def csound_name_default(
            self, *, name: str = None, type: int = None) -> str:  # pylint: disable=redefined-builtin
        if name is None:
            name = self.name

        if type is None:
            type = self.type

        if type == node_db.PortDescription.EVENTS:
            return '1'
        else:
            return self.csound_name_prefix(type=type) + name.capitalize()


class CustomCSound(_model.CustomCSound):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.__listeners = core.ListenerMap[int]()

        self.__orchestra_preamble = None  # type: str
        self.orchestra_preamble_changed = core.Callback[music.PropertyChange[str]]()

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

        self.__update_orchestra_preamble()

        self.description_changed.add(lambda *_: self.__update_orchestra_preamble())

        for port in self.ports:
            self.__add_port(None, port)
        self.ports_changed.add(self.__ports_changed)

    def __ports_changed(self, change: music.PropertyChange) -> None:
        if isinstance(change, music.PropertyListInsert):
            self.__add_port(change, change.new_value)
        elif isinstance(change, music.PropertyListDelete):
            self.__remove_port(change, change.old_value)
        else:
            raise TypeError("Unsupported change type %s" % type(change))

        self.description_changed.call(change)

    def __add_port(self, change: music.PropertyChange, port: CustomCSoundPort) -> None:
        self.__listeners[port.id] = port.object_changed.add(self.description_changed.call)
        self.description_changed.call(change)

    def __remove_port(self, change: music.PropertyChange, port: CustomCSoundPort) -> None:
        del self.__listeners[port.id]
        self.description_changed.call(change)

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
    def full_orchestra(self) -> str:
        return (self.__orchestra_preamble or '') + '\n\n' + (self.orchestra or '')

    @property
    def orchestra_preamble(self) -> str:
        return self.__orchestra_preamble

    def __update_orchestra_preamble(self) -> None:
        lines = []
        lines.append('0dbfs = 1.0')
        lines.append('ksmps = 32')
        lines.append('nchnls = 2')

        for port_desc in self.description.ports:
            if port_desc.types[0] in (node_db.PortDescription.AUDIO,
                                      node_db.PortDescription.KRATE_CONTROL,
                                      node_db.PortDescription.ARATE_CONTROL):
                if port_desc.direction == node_db.PortDescription.INPUT:
                    lines.append(
                        '%s chnexport "%s", 1' % (port_desc.csound_name, port_desc.name))
                else:
                    assert port_desc.direction == node_db.PortDescription.OUTPUT
                    lines.append(
                        '%s chnexport "%s", 2' % (port_desc.csound_name, port_desc.name))

        preamble = '\n'.join(lines)
        old_preamble = self.__orchestra_preamble

        if preamble != old_preamble:
            self.__orchestra_preamble = preamble
            self.orchestra_preamble_changed.call(
                music.PropertyValueChange(self, 'orchestra_preamble', old_preamble, preamble))

    @property
    def description(self) -> node_db.NodeDescription:
        desc = node_db.NodeDescription()
        desc.CopyFrom(node_description.CustomCSoundDescription)

        for port in self.ports:
            port_desc = desc.ports.add(
                name=port.name,
                display_name=port.display_name or port.name,
                types=[port.type],
                direction=port.direction,
                csound_name=port.csound_name,
            )
            if port.type in (node_db.PortDescription.KRATE_CONTROL,
                             node_db.PortDescription.ARATE_CONTROL):
                port_desc.float_value.min = 0.0
                port_desc.float_value.max = 1.0
                port_desc.float_value.default = 0.0

        return desc

    def create_port(self, index: int, name: str) -> CustomCSoundPort:
        port = self._pool.create(
            CustomCSoundPort,
            name=name,
            csound_name='ga' + name.capitalize(),
            type=node_db.PortDescription.AUDIO,
            direction=node_db.PortDescription.OUTPUT)
        self.ports.insert(index, port)
        return port

    def delete_port(self, port: CustomCSoundPort) -> None:
        port.remove_connections()
        del self.ports[port.index]
