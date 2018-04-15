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

# TODO: pylint-unclean
# mypy: loose

import logging
import random
from typing import Dict  # pylint: disable=unused-import

from noisicaa import core
from noisicaa import audioproc
from typing import cast

from . import model
from . import state
from . import commands
from . import base_track
from . import pipeline_graph
from . import misc

logger = logging.getLogger(__name__)


class AddControlPoint(commands.Command):
    time = core.Property(audioproc.MusicalTime)
    value = core.Property(float)

    def __init__(self, time=None, value=None, state=None):
        super().__init__(state=state)
        if state is None:
            self.time = time
            self.value = value

    def run(self, track):
        assert isinstance(track, ControlTrack)

        for insert_index, point in enumerate(track.points):
            if point.time == self.time:
                raise ValueError("Duplicate control point")
            if point.time > self.time:
                break
        else:
            insert_index = len(track.points)

        track.points.insert(
            insert_index,
            ControlPoint(time=self.time, value=self.value))

commands.Command.register_command(AddControlPoint)


class RemoveControlPoint(commands.Command):
    point_id = core.Property(str)

    def __init__(self, point_id=None, state=None):
        super().__init__(state=state)
        if state is None:
            self.point_id = point_id

    def run(self, track):
        assert isinstance(track, ControlTrack)

        root = track.root
        point = root.get_object(self.point_id)
        assert point.is_child_of(track)

        del track.points[point.index]

commands.Command.register_command(RemoveControlPoint)


class MoveControlPoint(commands.Command):
    point_id = core.Property(str)
    time = core.Property(audioproc.MusicalTime, allow_none=True)
    value = core.Property(float, allow_none=True)

    def __init__(self, point_id=None, time=None, value=None, state=None):
        super().__init__(state=state)
        if state is None:
            self.point_id = point_id
            self.time = time
            self.value = value

    def run(self, track):
        assert isinstance(track, ControlTrack)

        root = track.root
        point = cast(ControlPoint, root.get_object(self.point_id))
        assert point.is_child_of(track)

        if self.time is not None:
            if not point.is_first:
                if self.time <= cast(ControlPoint, point.prev_sibling).time:
                    raise ValueError("Control point out of order.")
            else:
                if self.time < audioproc.MusicalTime(0, 4):
                    raise ValueError("Control point out of order.")

            if not point.is_last:
                if self.time >= cast(ControlPoint, point.next_sibling).time:
                    raise ValueError("Control point out of order.")

            point.time = self.time

        if self.value is not None:
            # TODO: check that value is in valid range.
            point.value = self.value

commands.Command.register_command(MoveControlPoint)


class ControlPoint(model.ControlPoint, state.StateBase):
    def __init__(self, time=None, value=None, state=None, **kwargs):
        super().__init__(state=state)

        if state is None:
            self.time = time
            self.value = value

state.StateBase.register_class(ControlPoint)


class ControlTrackConnector(base_track.TrackConnector):
    def __init__(self, *, node_id, **kwargs):
        super().__init__(**kwargs)

        self.__node_id = node_id
        self.__listeners = {}  # type: Dict[str, core.Listener]
        self.__point_ids = {}  # type: Dict[str, int]

    def _init_internal(self):
        for point in self._track.points:
            self.__add_point(point)

        self.__listeners['points'] = self._track.listeners.add(
            'points', self.__points_list_changed)

    def close(self):
        for listener in self.__listeners.values():
            listener.remove()
        self.__listeners.clear()

        super().close()

    def __points_list_changed(self, change):
        if isinstance(change, core.PropertyListInsert):
            self.__add_point(change.new_value)

        elif isinstance(change, core.PropertyListDelete):
            self.__remove_point(change.old_value)

        else:
            raise TypeError(
                "Unsupported change type %s" % type(change))

    def __add_point(self, point):
        point_id = self.__point_ids[point.id] = random.getrandbits(64)

        self._emit_message(
            audioproc.ProcessorMessage(
                node_id=self.__node_id,
                cvgenerator_add_control_point=audioproc.ProcessorMessage.CVGeneratorAddControlPoint(
                    id=point_id,
                    time=point.time.to_proto(),
                    value=point.value)))

        self.__listeners['cp:%s:time' % point.id] = point.listeners.add(
            'time', lambda _: self.__point_changed(point))

        self.__listeners['cp:%s:value' % point.id] = point.listeners.add(
            'value', lambda _: self.__point_changed(point))

    def __remove_point(self, point):
        point_id = self.__point_ids[point.id]

        self._emit_message(
            audioproc.ProcessorMessage(
                node_id=self.__node_id,
                cvgenerator_remove_control_point=(
                    audioproc.ProcessorMessage.CVGeneratorRemoveControlPoint(id=point_id))))

        self.__listeners.pop('cp:%s:time' % point.id).remove()
        self.__listeners.pop('cp:%s:value' % point.id).remove()

    def __point_changed(self, point):
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


class ControlTrack(model.ControlTrack, base_track.Track):
    def __init__(self, state=None, **kwargs):
        super().__init__(state=state, **kwargs)

    def create_track_connector(self, **kwargs):
        return ControlTrackConnector(
            track=self,
            node_id=self.generator_name,
            **kwargs)

    @property
    def mixer_name(self):
        return self.parent_mixer_name

    @property
    def mixer_node(self):
        return self.parent_mixer_node

    @property
    def generator_name(self):
        return '%s-generator' % self.id

    @property
    def generator_node(self):
        if self.generator_id is None:
            raise ValueError("No generator node found.")
        return self.root.get_object(self.generator_id)

    def add_pipeline_nodes(self):
        generator_node = pipeline_graph.CVGeneratorPipelineGraphNode(
            name="Control Value",
            graph_pos=self.parent_mixer_node.graph_pos - misc.Pos2F(200, 0),
            track=self)
        self.project.add_pipeline_graph_node(generator_node)
        self.generator_id = generator_node.id

    def remove_pipeline_nodes(self):
        self.project.remove_pipeline_graph_node(self.generator_node)
        self.generator_id = None


state.StateBase.register_class(ControlTrack)
