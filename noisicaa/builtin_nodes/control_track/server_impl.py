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
import random
from typing import cast, Any, Dict, MutableSequence, Optional, Callable

from google.protobuf import message as protobuf

from noisicaa.core.typing_extra import down_cast
from noisicaa import audioproc
from noisicaa import model
from noisicaa import core
from noisicaa.music import commands
from noisicaa.music import pmodel
from noisicaa.music import node_connector
from noisicaa.music import base_track
from noisicaa.builtin_nodes import commands_registry_pb2
from . import commands_pb2
from . import model as control_track_model
from . import processor_messages

logger = logging.getLogger(__name__)


class AddControlPoint(commands.Command):
    proto_type = 'add_control_point'
    proto_ext = commands_registry_pb2.add_control_point

    def run(self, project: pmodel.Project, pool: pmodel.Pool, pb: protobuf.Message) -> None:
        pb = down_cast(commands_pb2.AddControlPoint, pb)
        track = down_cast(ControlTrack, pool[self.proto.command.target])

        insert_time = audioproc.MusicalTime.from_proto(pb.time)
        for insert_index, point in enumerate(track.points):
            if point.time == insert_time:
                raise ValueError("Duplicate control point")
            if point.time > insert_time:
                break
        else:
            insert_index = len(track.points)

        track.points.insert(
            insert_index,
            pool.create(ControlPoint, time=insert_time, value=pb.value))

commands.Command.register_command(AddControlPoint)


class RemoveControlPoint(commands.Command):
    proto_type = 'remove_control_point'
    proto_ext = commands_registry_pb2.remove_control_point

    def run(self, project: pmodel.Project, pool: pmodel.Pool, pb: protobuf.Message) -> None:
        pb = down_cast(commands_pb2.RemoveControlPoint, pb)
        track = down_cast(ControlTrack, pool[self.proto.command.target])

        point = down_cast(ControlPoint, pool[pb.point_id])
        assert point.is_child_of(track)

        del track.points[point.index]

commands.Command.register_command(RemoveControlPoint)


class MoveControlPoint(commands.Command):
    proto_type = 'move_control_point'
    proto_ext = commands_registry_pb2.move_control_point

    def run(self, project: pmodel.Project, pool: pmodel.Pool, pb: protobuf.Message) -> None:
        pb = down_cast(commands_pb2.MoveControlPoint, pb)
        track = down_cast(ControlTrack, pool[self.proto.command.target])

        point = down_cast(ControlPoint, pool[pb.point_id])
        assert point.is_child_of(track)

        if pb.HasField('time'):
            new_time = audioproc.MusicalTime.from_proto(pb.time)
            if not point.is_first:
                if new_time <= cast(ControlPoint, point.prev_sibling).time:
                    raise ValueError("Control point out of order.")
            else:
                if new_time < audioproc.MusicalTime(0, 4):
                    raise ValueError("Control point out of order.")

            if not point.is_last:
                if new_time >= cast(ControlPoint, point.next_sibling).time:
                    raise ValueError("Control point out of order.")

            point.time = new_time

        if pb.HasField('value'):
            # TODO: check that value is in valid range.
            point.value = pb.value

commands.Command.register_command(MoveControlPoint)


class ControlTrackConnector(node_connector.NodeConnector):
    _node = None  # type: ControlTrack

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.__node_id = self._node.pipeline_node_id
        self.__listeners = {}  # type: Dict[str, core.Listener]
        self.__point_ids = {}  # type: Dict[int, int]

    def _init_internal(self) -> None:
        for point in self._node.points:
            self.__add_point(point)

        self.__listeners['points'] = self._node.points_changed.add(
            self.__points_list_changed)

    def close(self) -> None:
        for listener in self.__listeners.values():
            listener.remove()
        self.__listeners.clear()

        super().close()

    def __points_list_changed(self, change: model.PropertyChange) -> None:
        if isinstance(change, model.PropertyListInsert):
            self.__add_point(change.new_value)

        elif isinstance(change, model.PropertyListDelete):
            self.__remove_point(change.old_value)

        else:
            raise TypeError("Unsupported change type %s" % type(change))

    def __add_point(self, point: 'ControlPoint') -> None:
        point_id = self.__point_ids[point.id] = random.getrandbits(64)

        self._emit_message(processor_messages.add_control_point(
            node_id=self.__node_id,
            id=point_id,
            time=point.time,
            value=point.value))

        self.__listeners['cp:%s:time' % point.id] = point.time_changed.add(
            lambda _: self.__point_changed(point))

        self.__listeners['cp:%s:value' % point.id] = point.value_changed.add(
            lambda _: self.__point_changed(point))

    def __remove_point(self, point: 'ControlPoint') -> None:
        point_id = self.__point_ids[point.id]

        self._emit_message(processor_messages.remove_control_point(
            node_id=self.__node_id,
            id=point_id))

        self.__listeners.pop('cp:%s:time' % point.id).remove()
        self.__listeners.pop('cp:%s:value' % point.id).remove()

    def __point_changed(self, point: 'ControlPoint') -> None:
        point_id = self.__point_ids[point.id]

        self._emit_message(processor_messages.remove_control_point(
            node_id=self.__node_id,
            id=point_id))
        self._emit_message(processor_messages.add_control_point(
            node_id=self.__node_id,
            id=point_id,
            time=point.time,
            value=point.value))


class ControlPoint(pmodel.ProjectChild, control_track_model.ControlPoint, pmodel.ObjectBase):
    def create(
            self, *,
            time: Optional[audioproc.MusicalTime] = None, value: float = None,
            **kwargs: Any) -> None:
        super().create(**kwargs)

        self.time = time
        self.value = value

    @property
    def time(self) -> audioproc.MusicalTime:
        return self.get_property_value('time')

    @time.setter
    def time(self, value: audioproc.MusicalTime) -> None:
        self.set_property_value('time', value)

    @property
    def value(self) -> float:
        return self.get_property_value('value')

    @value.setter
    def value(self, value: float) -> None:
        self.set_property_value('value', value)


class ControlTrack(base_track.Track, control_track_model.ControlTrack, pmodel.ObjectBase):
    @property
    def points(self) -> MutableSequence[ControlPoint]:
        return self.get_property_value('points')

    def create_node_connector(
            self, message_cb: Callable[[audioproc.ProcessorMessage], None]
    ) -> ControlTrackConnector:
        return ControlTrackConnector(node=self, message_cb=message_cb)
