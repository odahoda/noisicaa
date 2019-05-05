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

from noisicaa import core
from noisicaa import audioproc
from noisicaa import node_db
from noisicaa import model_base
from noisicaa.music import base_track
from noisicaa.music import node_connector
from noisicaa.music import model
from noisicaa.builtin_nodes import model_registry_pb2
from . import node_description
from . import processor_messages

logger = logging.getLogger(__name__)


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

    def __points_list_changed(self, change: model_base.PropertyChange) -> None:
        if isinstance(change, model_base.PropertyListInsert):
            self.__add_point(change.new_value)

        elif isinstance(change, model_base.PropertyListDelete):
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


class ControlPoint(model.ProjectChild):
    class ControlPointSpec(model_base.ObjectSpec):
        proto_type = 'control_point'
        proto_ext = model_registry_pb2.control_point

        time = model_base.WrappedProtoProperty(audioproc.MusicalTime)
        value = model_base.Property(float)

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.time_changed = core.Callback[model_base.PropertyChange[audioproc.MusicalTime]]()
        self.value_changed = core.Callback[model_base.PropertyChange[float]]()

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
        if self.parent is not None:
            if not self.is_first:
                if value <= cast(ControlPoint, self.prev_sibling).time:
                    raise ValueError("Control point out of order.")
            else:
                if value < audioproc.MusicalTime(0, 4):
                    raise ValueError("Control point out of order.")

            if not self.is_last:
                if value >= cast(ControlPoint, self.next_sibling).time:
                    raise ValueError("Control point out of order.")

        self.set_property_value('time', value)

    @property
    def value(self) -> float:
        return self.get_property_value('value')

    @value.setter
    def value(self, value: float) -> None:
        self.set_property_value('value', value)


class ControlTrack(base_track.Track):
    class ControlTrackSpec(model_base.ObjectSpec):
        proto_type = 'control_track'
        proto_ext = model_registry_pb2.control_track

        points = model_base.ObjectListProperty(ControlPoint)

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.points_changed = core.Callback[model_base.PropertyListChange[ControlPoint]]()

    @property
    def description(self) -> node_db.NodeDescription:
        return node_description.ControlTrackDescription

    @property
    def points(self) -> MutableSequence[ControlPoint]:
        return self.get_property_value('points')

    def create_node_connector(
            self,
            message_cb: Callable[[audioproc.ProcessorMessage], None],
            audioproc_client: audioproc.AbstractAudioProcClient,
    ) -> ControlTrackConnector:
        return ControlTrackConnector(
            node=self, message_cb=message_cb, audioproc_client=audioproc_client)

    def create_control_point(self, time: audioproc.MusicalTime, value: float) -> ControlPoint:
        for insert_index, point in enumerate(self.points):
            if point.time == time:
                raise ValueError("Duplicate control point")
            if point.time > time:
                break
        else:
            insert_index = len(self.points)

        control_point = self._pool.create(ControlPoint, time=time, value=value)
        self.points.insert(insert_index, control_point)
        return control_point

    def delete_control_point(self, point: ControlPoint) -> None:
        del self.points[point.index]
