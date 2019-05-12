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
from typing import Any, Iterator, Callable, Dict

from noisicaa.core.typing_extra import down_cast
from noisicaa import core
from noisicaa import audioproc
from noisicaa import node_db
from noisicaa.music import node_connector
from . import node_description
from . import model_pb2
from . import processor_pb2
from . import _model

logger = logging.getLogger(__name__)


class Connector(node_connector.NodeConnector):
    _node = None  # type: MidiCCtoCV

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.__node_id = self._node.pipeline_node_id
        self.__listeners = core.ListenerMap[str]()
        self.add_cleanup_function(self.__listeners.cleanup)

    def _init_internal(self) -> None:
        self.__listeners['node_messages'] = self._audioproc_client.node_messages.add(
            self.__node_id, self.__node_message)

    def __node_message(self, msg: Dict[str, Any]) -> None:
        cc_urid = 'http://noisicaa.odahoda.de/lv2/processor_cc_to_cv#cc'
        if cc_urid in msg:
            channel_idx, value = msg[cc_urid]
            self._node.set_controller_value(channel_idx, value)


class MidiCCtoCVChannel(_model.MidiCCtoCVChannel):
    def create(
            self, *,
            type: model_pb2.MidiCCtoCVChannel.Type = model_pb2.MidiCCtoCVChannel.CONTROLLER,  # pylint: disable=redefined-builtin
            **kwargs: Any
    ) -> None:
        super().create(**kwargs)

        self.type = type

    def setup(self) -> None:
        super().setup()

        self.type_changed.add(lambda _: self.midi_cc_to_cv.update_spec())
        self.midi_channel_changed.add(lambda _: self.midi_cc_to_cv.update_spec())
        self.midi_controller_changed.add(lambda _: self.midi_cc_to_cv.update_spec())
        self.min_value_changed.add(lambda _: self.midi_cc_to_cv.update_spec())
        self.max_value_changed.add(lambda _: self.midi_cc_to_cv.update_spec())
        self.log_scale_changed.add(lambda _: self.midi_cc_to_cv.update_spec())
        self.log_scale_changed.add(lambda _: self.midi_cc_to_cv.update_spec())

    @property
    def midi_cc_to_cv(self) -> 'MidiCCtoCV':
        return down_cast(MidiCCtoCV, self.parent)


class MidiCCtoCV(_model.MidiCCtoCV):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.__controller_values = {}  # type: Dict[int, int]

    def create(self, **kwargs: Any) -> None:
        super().create(**kwargs)

        channel = self._pool.create(
            MidiCCtoCVChannel,
            type=model_pb2.MidiCCtoCVChannel.CONTROLLER)
        self.channels.append(channel)

    def setup(self) -> None:
        super().setup()

        self.channels_changed.add(self.description_changed.call)
        self.channels_changed.add(lambda _: self.update_spec())

    def get_initial_parameter_mutations(self) -> Iterator[audioproc.Mutation]:
        yield from super().get_initial_parameter_mutations()
        yield self.__get_spec_mutation()

    def update_spec(self) -> None:
        if self.attached_to_project:
            self.project.handle_pipeline_mutation(
                self.__get_spec_mutation())

    def __get_spec_mutation(self) -> audioproc.Mutation:
        params = audioproc.NodeParameters()
        spec = params.Extensions[processor_pb2.midi_cc_to_cv_spec]
        for channel_idx, channel in enumerate(self.channels):
            channel_spec = spec.channels.add()
            channel_spec.midi_channel = channel.midi_channel
            channel_spec.midi_controller = channel.midi_controller
            channel_spec.initial_value = self.__controller_values.get(channel_idx, 0)
            channel_spec.min_value = channel.min_value
            channel_spec.max_value = channel.max_value
            channel_spec.log_scale = channel.log_scale

        return audioproc.Mutation(
            set_node_parameters=audioproc.SetNodeParameters(
                node_id=self.pipeline_node_id,
                parameters=params))

    def create_node_connector(
            self, message_cb: Callable[[audioproc.ProcessorMessage], None],
            audioproc_client: audioproc.AbstractAudioProcClient,
    ) -> Connector:
        return Connector(
            node=self,
            message_cb=message_cb,
            audioproc_client=audioproc_client)

    def set_controller_value(self, channel_idx: int, value: int) -> None:
        self.__controller_values[channel_idx] = value

    @property
    def description(self) -> node_db.NodeDescription:
        node_desc = node_db.NodeDescription()
        node_desc.CopyFrom(node_description.MidiCCtoCVDescription)

        for idx in range(len(self.channels)):
            node_desc.ports.add(
                name='channel%d' % (idx + 1),
                direction=node_db.PortDescription.OUTPUT,
                type=node_db.PortDescription.ARATE_CONTROL,
            )

        return node_desc

    def create_channel(self, index: int) -> MidiCCtoCVChannel:
        channel = self._pool.create(
            MidiCCtoCVChannel,
            type=model_pb2.MidiCCtoCVChannel.CONTROLLER)
        self.channels.insert(index, channel)
        return channel

    def delete_channel(self, channel: MidiCCtoCVChannel) -> None:
        del self.channels[channel.index]
