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
from typing import Any, Iterator, MutableSequence, Callable, Dict

from noisicaa.core.typing_extra import down_cast
from noisicaa import core
from noisicaa import audioproc
from noisicaa import node_db
from noisicaa import model_base
from noisicaa.music import graph
from noisicaa.music import node_connector
from noisicaa.music import commands
from noisicaa.music import model
from noisicaa.builtin_nodes import model_registry_pb2
from noisicaa.builtin_nodes import commands_registry_pb2
from . import node_description
from . import model_pb2
from . import commands_pb2
from . import processor_pb2

logger = logging.getLogger(__name__)


class UpdateMidiCCtoCV(commands.Command):
    proto_type = 'update_midi_cc_to_cv'
    proto_ext = commands_registry_pb2.update_midi_cc_to_cv

    def run(self) -> None:
        pb = down_cast(commands_pb2.UpdateMidiCCtoCV, self.pb)
        down_cast(MidiCCtoCV, self.pool[pb.node_id])


class CreateMidiCCtoCVChannel(commands.Command):
    proto_type = 'create_midi_cc_to_cv_channel'
    proto_ext = commands_registry_pb2.create_midi_cc_to_cv_channel

    def run(self) -> None:
        pb = down_cast(commands_pb2.CreateMidiCCtoCVChannel, self.pb)
        node = down_cast(MidiCCtoCV, self.pool[pb.node_id])

        if pb.HasField('index'):
            index = pb.index
        else:
            index = len(node.channels)

        channel = self.pool.create(
            MidiCCtoCVChannel,
            type=model_pb2.MidiCCtoCVChannel.CONTROLLER)
        node.channels.insert(index, channel)


class UpdateMidiCCtoCVChannel(commands.Command):
    proto_type = 'update_midi_cc_to_cv_channel'
    proto_ext = commands_registry_pb2.update_midi_cc_to_cv_channel

    def run(self) -> None:
        pb = down_cast(commands_pb2.UpdateMidiCCtoCVChannel, self.pb)
        channel = down_cast(MidiCCtoCVChannel, self.pool[pb.channel_id])

        if pb.HasField('set_type'):
            channel.type = pb.set_type

        if pb.HasField('set_midi_channel'):
            channel.midi_channel = pb.set_midi_channel

        if pb.HasField('set_midi_controller'):
            channel.midi_controller = pb.set_midi_controller

        if pb.HasField('set_min_value'):
            channel.min_value = pb.set_min_value

        if pb.HasField('set_max_value'):
            channel.max_value = pb.set_max_value

        if pb.HasField('set_log_scale'):
            channel.log_scale = pb.set_log_scale


class DeleteMidiCCtoCVChannel(commands.Command):
    proto_type = 'delete_midi_cc_to_cv_channel'
    proto_ext = commands_registry_pb2.delete_midi_cc_to_cv_channel

    def run(self) -> None:
        pb = down_cast(commands_pb2.DeleteMidiCCtoCVChannel, self.pb)
        channel = down_cast(MidiCCtoCVChannel, self.pool[pb.channel_id])
        node = down_cast(MidiCCtoCV, channel.parent)

        del node.channels[channel.index]


class Connector(node_connector.NodeConnector):
    _node = None  # type: MidiCCtoCV

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.__node_id = self._node.pipeline_node_id
        self.__listeners = {}  # type: Dict[str, core.Listener]

    def _init_internal(self) -> None:
        self.__listeners['node_messages'] = self._audioproc_client.node_messages.add(
            self.__node_id, self.__node_message)

    def close(self) -> None:
        for listener in self.__listeners.values():
            listener.remove()
        self.__listeners.clear()

        super().close()

    def __node_message(self, msg: Dict[str, Any]) -> None:
        cc_urid = 'http://noisicaa.odahoda.de/lv2/processor_cc_to_cv#cc'
        if cc_urid in msg:
            channel_idx, value = msg[cc_urid]
            self._node.set_controller_value(channel_idx, value)


class MidiCCtoCVChannel(model.ProjectChild):
    class MidiCCtoCVChannelSpec(model_base.ObjectSpec):
        proto_type = 'midi_cc_to_cv_channel'
        proto_ext = model_registry_pb2.midi_cc_to_cv_channel

        type = model_base.Property(model_pb2.MidiCCtoCVChannel.Type)
        midi_channel = model_base.Property(int, default=0)
        midi_controller = model_base.Property(int, default=0)
        min_value = model_base.Property(float, default=0.0)
        max_value = model_base.Property(float, default=1.0)
        log_scale = model_base.Property(bool, default=False)

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.type_changed = core.Callback[model_base.PropertyChange[int]]()
        self.midi_channel_changed = core.Callback[model_base.PropertyChange[int]]()
        self.midi_controller_changed = core.Callback[model_base.PropertyChange[int]]()
        self.min_value_changed = core.Callback[model_base.PropertyChange[float]]()
        self.max_value_changed = core.Callback[model_base.PropertyChange[float]]()
        self.log_scale_changed = core.Callback[model_base.PropertyChange[bool]]()

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
    def type(self) -> model_pb2.MidiCCtoCVChannel.Type:
        return self.get_property_value('type')

    @type.setter
    def type(self, value: model_pb2.MidiCCtoCVChannel.Type) -> None:
        self.set_property_value('type', value)

    @property
    def midi_channel(self) -> int:
        return self.get_property_value('midi_channel')

    @midi_channel.setter
    def midi_channel(self, value: int) -> None:
        self.set_property_value('midi_channel', value)

    @property
    def midi_controller(self) -> int:
        return self.get_property_value('midi_controller')

    @midi_controller.setter
    def midi_controller(self, value: int) -> None:
        self.set_property_value('midi_controller', value)

    @property
    def min_value(self) -> float:
        return self.get_property_value('min_value')

    @min_value.setter
    def min_value(self, value: float) -> None:
        self.set_property_value('min_value', value)

    @property
    def max_value(self) -> float:
        return self.get_property_value('max_value')

    @max_value.setter
    def max_value(self, value: float) -> None:
        self.set_property_value('max_value', value)

    @property
    def log_scale(self) -> bool:
        return self.get_property_value('log_scale')

    @log_scale.setter
    def log_scale(self, value: bool) -> None:
        self.set_property_value('log_scale', value)

    @property
    def midi_cc_to_cv(self) -> 'MidiCCtoCV':
        return down_cast(MidiCCtoCV, self.parent)


class MidiCCtoCV(graph.BaseNode):
    class MidiCCtoCVSpec(model_base.ObjectSpec):
        proto_type = 'midi_cc_to_cv'
        proto_ext = model_registry_pb2.midi_cc_to_cv

        channels = model_base.ObjectListProperty(MidiCCtoCVChannel)

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.__controller_values = {}  # type: Dict[int, int]

        self.channels_changed = core.Callback[model_base.PropertyListChange[MidiCCtoCVChannel]]()

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

    @property
    def channels(self) -> MutableSequence[MidiCCtoCVChannel]:
        return self.get_property_value('channels')

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
