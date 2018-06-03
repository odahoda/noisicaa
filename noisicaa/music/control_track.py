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
import random
from typing import cast, Any, Dict, Optional  # pylint: disable=unused-import

from google.protobuf import message as protobuf

from noisicaa.core.typing_extra import down_cast
from noisicaa import audioproc
from noisicaa import model
from noisicaa import core  # pylint: disable=unused-import
from . import pmodel
from . import base_track
from . import pipeline_graph
from . import commands
from . import commands_pb2

logger = logging.getLogger(__name__)


class AddControlPoint(commands.Command):
    proto_type = 'add_control_point'

    def run(self, project: pmodel.Project, pool: pmodel.Pool, pb: protobuf.Message) -> None:
        pb = down_cast(commands_pb2.AddControlPoint, pb)
        track = down_cast(pmodel.ControlTrack, pool[self.proto.command.target])

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

    def run(self, project: pmodel.Project, pool: pmodel.Pool, pb: protobuf.Message) -> None:
        pb = down_cast(commands_pb2.RemoveControlPoint, pb)
        track = down_cast(pmodel.ControlTrack, pool[self.proto.command.target])

        point = down_cast(pmodel.ControlPoint, pool[pb.point_id])
        assert point.is_child_of(track)

        del track.points[point.index]

commands.Command.register_command(RemoveControlPoint)


class MoveControlPoint(commands.Command):
    proto_type = 'move_control_point'

    def run(self, project: pmodel.Project, pool: pmodel.Pool, pb: protobuf.Message) -> None:
        pb = down_cast(commands_pb2.MoveControlPoint, pb)
        track = down_cast(pmodel.ControlTrack, pool[self.proto.command.target])

        point = down_cast(pmodel.ControlPoint, pool[pb.point_id])
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


class ControlPoint(pmodel.ControlPoint):
    def create(
            self, *,
            time: Optional[audioproc.MusicalTime] = None, value: float = None,
            **kwargs: Any) -> None:
        super().create(**kwargs)

        self.time = time
        self.value = value


class ControlTrackConnector(base_track.TrackConnector):
    _track = None  # type: ControlTrack

    def __init__(self, *, node_id: str, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.__node_id = node_id
        self.__listeners = {}  # type: Dict[str, core.Listener]
        self.__point_ids = {}  # type: Dict[int, int]

    def _init_internal(self) -> None:
        for point in self._track.points:
            self.__add_point(point)

        self.__listeners['points'] = self._track.points_changed.add(
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

    def __add_point(self, point: pmodel.ControlPoint) -> None:
        point_id = self.__point_ids[point.id] = random.getrandbits(64)

        self._emit_message(
            audioproc.ProcessorMessage(
                node_id=self.__node_id,
                cvgenerator_add_control_point=audioproc.ProcessorMessage.CVGeneratorAddControlPoint(
                    id=point_id,
                    time=point.time.to_proto(),
                    value=point.value)))

        self.__listeners['cp:%s:time' % point.id] = point.time_changed.add(
            lambda _: self.__point_changed(point))

        self.__listeners['cp:%s:value' % point.id] = point.value_changed.add(
            lambda _: self.__point_changed(point))

    def __remove_point(self, point: pmodel.ControlPoint) -> None:
        point_id = self.__point_ids[point.id]

        self._emit_message(
            audioproc.ProcessorMessage(
                node_id=self.__node_id,
                cvgenerator_remove_control_point=(
                    audioproc.ProcessorMessage.CVGeneratorRemoveControlPoint(id=point_id))))

        self.__listeners.pop('cp:%s:time' % point.id).remove()
        self.__listeners.pop('cp:%s:value' % point.id).remove()

    def __point_changed(self, point: pmodel.ControlPoint) -> None:
        point_id = self.__point_ids[point.id]

        self._emit_message(
            audioproc.ProcessorMessage(
                node_id=self.__node_id,
                cvgenerator_remove_control_point=(
                    audioproc.ProcessorMessage.CVGeneratorRemoveControlPoint(id=point_id))))
        self._emit_message(
            audioproc.ProcessorMessage(
                node_id=self.__node_id,
                cvgenerator_add_control_point=audioproc.ProcessorMessage.CVGeneratorAddControlPoint(
                    id=point_id,
                    time=point.time.to_proto(),
                    value=point.value)))


class ControlTrack(pmodel.ControlTrack, base_track.Track):
    def create_track_connector(self, **kwargs: Any) -> ControlTrackConnector:
        return ControlTrackConnector(
            track=self,
            node_id=self.generator_name,
            **kwargs)

    @property
    def mixer_name(self) -> str:
        return self.parent_audio_sink_name

    @property
    def mixer_node(self) -> pmodel.BasePipelineGraphNode:
        return self.parent_audio_sink_node

    @mixer_node.setter
    def mixer_node(self, value: pmodel.TrackMixerPipelineGraphNode) -> None:
        raise RuntimeError

    @property
    def generator_name(self) -> str:
        return '%016x-generator' % self.id

    def add_pipeline_nodes(self) -> None:
        generator_node = self._pool.create(
            pipeline_graph.CVGeneratorPipelineGraphNode,
            name="Control Value",
            graph_pos=self.parent_audio_sink_node.graph_pos - model.Pos2F(200, 0),
            track=self)
        self.project.add_pipeline_graph_node(generator_node)
        self.generator_node = generator_node

    def remove_pipeline_nodes(self) -> None:
        self.project.remove_pipeline_graph_node(self.generator_node)
        self.generator_node = None
