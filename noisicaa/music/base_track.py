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
from typing import Any, Optional, Callable, Dict, List, Type  # pylint: disable=unused-import

from noisicaa.core.typing_extra import down_cast
from noisicaa import core
from noisicaa import audioproc

from . import model
from . import commands
from . import pipeline_graph
from . import misc
from . import state as state_lib
from . import pitch as pitch_lib
from . import project_iface

logger = logging.getLogger(__name__)


class MoveTrack(commands.Command):
    direction = core.Property(int)

    def __init__(
            self, direction: Optional[int] = None, state: Optional[state_lib.State] = None) -> None:
        super().__init__(state=state)
        if state is None:
            self.direction = direction

    def run(self, target: state_lib.StateBase) -> None:
        track = down_cast(Track, target)
        assert not track.is_master_group
        parent = down_cast(model.TrackGroup, track.parent)

        if self.direction == 0:
            raise ValueError("No direction given.")

        if self.direction < 0:
            if track.index == 0:
                raise ValueError("Can't move first track up.")
            new_pos = track.index - 1
            del parent.tracks[track.index]
            parent.tracks.insert(new_pos, track)

        elif self.direction > 0:
            if track.index == len(parent.tracks) - 1:
                raise ValueError("Can't move last track down.")
            new_pos = track.index + 1
            del parent.tracks[track.index]
            parent.tracks.insert(new_pos, track)

commands.Command.register_command(MoveTrack)


class ReparentTrack(commands.Command):
    new_parent = core.Property(str)
    # TODO: this clashes with the index attribute of ObjectBase
    index = core.Property(int)  # type: ignore

    def __init__(
            self, new_parent: Optional[str] = None, index: Optional[int] = None,
            state: Optional[state_lib.State] = None) -> None:
        super().__init__(state=state)
        if state is None:
            self.new_parent = new_parent
            self.index = index

    def run(self, target: state_lib.StateBase) -> None:
        track = down_cast(Track, target)
        assert not track.is_master_group

        old_parent = down_cast(model.TrackGroup, track.parent)
        new_parent = down_cast(model.TrackGroup, track.root.get_object(self.new_parent))
        assert new_parent.is_child_of(track.project)
        assert isinstance(new_parent, model.TrackGroup)

        assert 0 <= self.index <= len(new_parent.tracks)

        del old_parent.tracks[track.index]
        new_parent.tracks.insert(self.index, track)

commands.Command.register_command(ReparentTrack)


class UpdateTrackProperties(commands.Command):
    name = core.Property(str, allow_none=True)
    visible = core.Property(bool, allow_none=True)
    muted = core.Property(bool, allow_none=True)
    gain = core.Property(float, allow_none=True)
    pan = core.Property(float, allow_none=True)

    # TODO: this only applies to ScoreTrack... use separate command for
    #   class specific properties?
    transpose_octaves = core.Property(int, allow_none=True)

    def __init__(
            self, name: Optional[str] = None, visible: Optional[bool] = None,
            muted: Optional[bool] = None, gain: Optional[float] = None,
            pan: Optional[float] = None, transpose_octaves: Optional[int] = None,
            state: Optional[state_lib.State] = None) -> None:
        super().__init__(state=state)
        if state is None:
            self.name = name
            self.visible = visible
            self.muted = muted
            self.gain = gain
            self.pan = pan
            self.transpose_octaves = transpose_octaves

    def run(self, target: state_lib.StateBase) -> None:
        track = down_cast(Track, target)

        if self.name is not None:
            track.name = self.name

        if self.visible is not None:
            track.visible = self.visible

        # TODO: broken, needs to increment generation
        # if self.muted is not None:
        #     track.muted = self.muted
        #     track.mixer_node.set_control_value('muted', float(self.muted))

        # if self.gain is not None:
        #     track.gain = self.gain
        #     track.mixer_node.set_control_value('gain', self.gain)

        # if self.pan is not None:
        #     track.pan = self.pan
        #     track.mixer_node.set_control_value('pan', self.pan)

        if self.transpose_octaves is not None:
            assert isinstance(track, model.ScoreTrack)
            track.transpose_octaves = self.transpose_octaves

commands.Command.register_command(UpdateTrackProperties)


class TrackConnector(object):
    def __init__(
            self, *, track: 'Track', message_cb: Callable[[audioproc.ProcessorMessage], None]
    ) -> None:
        self._track = track
        self.__message_cb = message_cb

        self.__initializing = True
        self.__initial_messages = []  # type: List[audioproc.ProcessorMessage]

    def init(self) -> List[audioproc.ProcessorMessage]:
        assert self.__initializing
        self._init_internal()
        self.__initializing = False
        messages = self.__initial_messages
        self.__initial_messages = None
        return messages

    def _init_internal(self) -> None:
        raise NotImplementedError

    def _emit_message(self, msg: audioproc.ProcessorMessage) -> None:
        if self.__initializing:
            self.__initial_messages.append(msg)
        else:
            self.__message_cb(msg)

    def close(self) -> None:
        pass


class Track(model.Track, state_lib.StateBase):
    def __init__(self, name: Optional[str] = None, state: Optional[state_lib.State] = None) -> None:
        super().__init__(state)

        if state is None:
            self.name = name

    def create_track_connector(self, **kwargs: Any) -> TrackConnector:
        raise NotImplementedError

    @property
    def parent_mixer_name(self) -> str:
        return down_cast(Track, self.parent).mixer_name

    @property
    def parent_mixer_node(self) -> pipeline_graph.PipelineGraphNode:
        return down_cast(Track, self.parent).mixer_node

    # TODO: the following are common to MeasuredTrack and TrackGroup, but not really
    # generic for all track types.

    @property
    def mixer_name(self) -> str:
        return '%s-track-mixer' % self.id

    @property
    def mixer_node(self) -> pipeline_graph.PipelineGraphNode:
        if self.mixer_id is None:
            raise ValueError("No mixer node found.")

        return down_cast(pipeline_graph.PipelineGraphNode, self.root.get_object(self.mixer_id))

    @property
    def relative_position_to_parent_mixer(self) -> misc.Pos2F:
        return misc.Pos2F(-200, self.index * 100)

    @property
    def default_mixer_name(self) -> str:
        return "Track Mixer"

    def add_pipeline_nodes(self) -> None:
        parent_mixer_node = self.parent_mixer_node

        project = down_cast(project_iface.IProject, self.project)

        mixer_node = pipeline_graph.TrackMixerPipelineGraphNode(
            name=self.default_mixer_name,
            graph_pos=(
                parent_mixer_node.graph_pos
                + self.relative_position_to_parent_mixer),
            track=self)
        project.add_pipeline_graph_node(mixer_node)
        self.mixer_id = mixer_node.id

        conn = pipeline_graph.PipelineGraphConnection(
            mixer_node, 'out:left', parent_mixer_node, 'in:left')
        project.add_pipeline_graph_connection(conn)

        conn = pipeline_graph.PipelineGraphConnection(
            mixer_node, 'out:right', parent_mixer_node, 'in:right')
        project.add_pipeline_graph_connection(conn)

    def remove_pipeline_nodes(self) -> None:
        project = down_cast(project_iface.IProject, self.project)
        project.remove_pipeline_graph_node(self.mixer_node)
        self.mixer_id = None


class Measure(model.Measure, state_lib.StateBase):
    @property
    def empty(self) -> bool:
        return False


class MeasureReference(model.MeasureReference, state_lib.StateBase):
    def __init__(
            self, measure_id: Optional[str] = None, state: Optional[state_lib.State] = None
    ) -> None:
        super().__init__(state)

        if state is None:
            self.measure_id = measure_id

state_lib.StateBase.register_class(MeasureReference)


class PianoRollInterval(object):
    def __init__(
            self, begin: audioproc.MusicalTime, end: audioproc.MusicalTime,
            pitch: pitch_lib.Pitch, velocity: int) -> None:
        self.id = random.getrandbits(64)
        self.begin = begin
        self.end = end
        self.pitch = pitch
        self.velocity = velocity

    def __str__(self) -> str:
        return '<PianoRollInterval id=%016x begin=%s end=%s pitch=%s velocity=%s>' % (
            self.id, self.begin, self.end, self.pitch, self.velocity)
    __repr__ = __str__

    def create_add_message(self, node_id: str) -> audioproc.ProcessorMessage:
        return audioproc.ProcessorMessage(
            node_id=node_id,
            pianoroll_add_interval=audioproc.ProcessorMessage.PianoRollAddInterval(
                id=self.id,
                start_time=self.begin.to_proto(),
                end_time=self.end.to_proto(),
                pitch=self.pitch.midi_note,
                velocity=self.velocity))

    def create_remove_message(self, node_id: str) -> audioproc.ProcessorMessage:
        return audioproc.ProcessorMessage(
            node_id=node_id,
            pianoroll_remove_interval=audioproc.ProcessorMessage.PianoRollRemoveInterval(
                id=self.id))


class MeasuredTrackConnector(TrackConnector):
    _track = None  # type: MeasuredTrack

    def __init__(self, *, node_id: str, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self._listeners = {}  # type: Dict[str, core.Listener]

        self.__node_id = node_id
        self.__measure_events = {}  # type: Dict[str, List[PianoRollInterval]]

    def _init_internal(self) -> None:
        time = audioproc.MusicalTime()
        for mref in self._track.measure_list:
            self.__add_measure(time, mref)
            time += mref.measure.duration

        self._listeners['measure_list'] = self._track.listeners.add(
            'measure_list', self.__measure_list_changed)
        self._add_track_listeners()

    def close(self) -> None:
        for listener in self._listeners.values():
            listener.remove()
        self._listeners.clear()

        super().close()

    def __add_event(self, event: PianoRollInterval) -> None:
        self._emit_message(event.create_add_message(self.__node_id))

    def __remove_event(self, event: PianoRollInterval) -> None:
        self._emit_message(event.create_remove_message(self.__node_id))

    def _add_track_listeners(self) -> None:
        pass

    def _add_measure_listeners(self, mref: model.MeasureReference) -> None:
        pass

    def _remove_measure_listeners(self, mref: model.MeasureReference) -> None:
        pass

    def _create_events(
            self, time: audioproc.MusicalTime, measure: model.Measure) -> List[PianoRollInterval]:
        raise NotImplementedError

    def _update_measure(self, time: audioproc.MusicalTime, mref: model.MeasureReference) -> None:
        mref = down_cast(MeasureReference, mref)

        events = self.__measure_events[mref.id]
        for event in events:
            self.__remove_event(event)
        events.clear()
        for event in self._create_events(time, mref.measure):
            self.__add_event(event)
            events.append(event)

    def _update_measure_range(
            self, begin: audioproc.MusicalTime, end: audioproc.MusicalTime) -> None:
        time = audioproc.MusicalTime()
        for mref in self._track.measure_list:
            if mref.index >= end:
                break

            if mref.index >= begin:
                self._update_measure(time, mref)

            time += mref.measure.duration

    def __measure_list_changed(self, change: core.PropertyChange) -> None:
        if isinstance(change, core.PropertyListInsert):
            time = audioproc.MusicalTime()
            for mref in self._track.measure_list:
                if mref.index == change.new_value.index:
                    assert mref is change.new_value
                    self.__add_measure(time, mref)
                elif mref.index > change.new_value.index:
                    self._update_measure(time, mref)

                time += mref.measure.duration

        elif isinstance(change, core.PropertyListDelete):
            mref = change.old_value
            self.__remove_measure(mref)
        else:
            raise TypeError(
                "Unsupported change type %s" % type(change))

    def __add_measure(self, time: audioproc.MusicalTime, mref: model.MeasureReference) -> None:
        mref = down_cast(MeasureReference, mref)
        assert mref.id not in self.__measure_events

        events = self.__measure_events[mref.id] = []
        for event in self._create_events(time, mref.measure):
            self.__add_event(event)
            events.append(event)

        self._listeners['measure:%s:ref' % mref.id] = mref.listeners.add(
            'measure_id', lambda _: self.__measure_id_changed(mref))
        self._add_measure_listeners(mref)

    def __remove_measure(self, mref: model.MeasureReference) -> None:
        mref = down_cast(MeasureReference, mref)

        self._remove_measure_listeners(mref)
        self._listeners.pop('measure:%s:ref' % mref.id).remove()

        for event in self.__measure_events.pop(mref.id):
            self.__remove_event(event)

    def __measure_id_changed(self, mref: model.MeasureReference) -> None:
        mref = down_cast(MeasureReference, mref)

        self._remove_measure_listeners(mref)
        self._listeners.pop('measure:%s:ref' % mref.id).remove()

        self._listeners['measure:%s:ref' % mref.id] = mref.listeners.add(
            'measure_id', lambda _: self.__measure_id_changed(mref))
        self._add_measure_listeners(mref)

        self._update_measure_range(mref.index, mref.index + 1)


class MeasuredTrack(model.MeasuredTrack, Track):  # pylint: disable=abstract-method
    measure_cls = None  # type: Type[Measure]

    def __init__(self, state: Optional[state_lib.State] = None, **kwargs: Any) -> None:
        super().__init__(state=state, **kwargs)

        if state is None:
            pass

        self.__listeners = {}  # type: Dict[str, core.Listener]

        for mref in self.measure_list:
            self.__add_measure(mref)

        self.listeners.add('measure_list', self.__measure_list_changed)

    def __measure_list_changed(self, change: core.PropertyChange) -> None:
        if isinstance(change, core.PropertyListInsert):
            self.__add_measure(change.new_value)
        elif isinstance(change, core.PropertyListDelete):
            self.__remove_measure(change.old_value)
        else:
            raise TypeError("Unsupported change type %s" % type(change))

    def __add_measure(self, mref: model.MeasureReference) -> None:
        mref = down_cast(MeasureReference, mref)
        self.__listeners['measure:%s:ref' % mref.id] = mref.listeners.add(
            'measure_id', lambda *_: self.__measure_id_changed(mref))
        self.listeners.call('duration_changed')

    def __remove_measure(self, mref: model.MeasureReference) -> None:
        mref = down_cast(MeasureReference, mref)
        self.__listeners.pop('measure:%s:ref' % mref.id).remove()
        self.listeners.call('duration_changed')

    def __measure_id_changed(self, mref: model.MeasureReference) -> None:
        mref = down_cast(MeasureReference, mref)
        self.listeners.call('duration_changed')

    def append_measure(self) -> None:
        self.insert_measure(-1)

    def insert_measure(self, idx: int) -> None:
        assert idx == -1 or (0 <= idx <= len(self.measure_list) - 1)

        if idx == -1:
            idx = len(self.measure_list)

        if idx == 0 and len(self.measure_list) > 0:
            ref_id = self.measure_list[0].measure_id
        elif idx > 0:
            ref_id = self.measure_list[idx-1].measure_id
        else:
            ref_id = None

        if ref_id is not None:
            for ref in self.measure_heap:
                if ref.id == ref_id:
                    break
            else:
                raise ValueError(ref_id)
        else:
            ref = None

        measure = self.create_empty_measure(ref)
        self.measure_heap.append(measure)
        self.measure_list.insert(idx, MeasureReference(measure_id=measure.id))

    def garbage_collect_measures(self) -> None:
        ref_counts = {measure.id: 0 for measure in self.measure_heap}

        for mref in self.measure_list:
            ref_counts[mref.measure_id] += 1

        measure_ids_to_delete = [
            measure_id for measure_id, ref_count in ref_counts.items()
            if ref_count == 0]
        indices_to_delete = [
            self.root.get_object(measure_id).index
            for measure_id in measure_ids_to_delete]
        for idx in sorted(indices_to_delete, reverse=True):
            del self.measure_heap[idx]

    def remove_measure(self, idx: int) -> None:
        del self.measure_list[idx]
        self.garbage_collect_measures()

    def create_empty_measure(self, ref: Optional[model.Measure]) -> Measure:  # pylint: disable=unused-argument
        return self.measure_cls()  # pylint: disable=not-callable
