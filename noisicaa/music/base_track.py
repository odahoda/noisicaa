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

import logging
import random

from noisicaa import core
from noisicaa import audioproc

from . import model
from . import state
from . import commands
from . import pipeline_graph
from . import misc

logger = logging.getLogger(__name__)


class MoveTrack(commands.Command):
    direction = core.Property(int)

    def __init__(self, direction=None, state=None):
        super().__init__(state=state)
        if state is None:
            self.direction = direction

    def run(self, track):
        assert isinstance(track, model.Track)
        assert not track.is_master_group
        parent = track.parent

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
    index = core.Property(int)

    def __init__(self, new_parent=None, index=None, state=None):
        super().__init__(state=state)
        if state is None:
            self.new_parent = new_parent
            self.index = index

    def run(self, track):
        assert isinstance(track, model.Track)

        assert not track.is_master_group

        new_parent = track.root.get_object(self.new_parent)
        assert new_parent.is_child_of(track.project)
        assert isinstance(new_parent, model.TrackGroup)

        assert 0 <= self.index <= len(new_parent.tracks)

        del track.parent.tracks[track.index]
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

    def __init__(self, name=None, visible=None, muted=None, gain=None, pan=None,
                 transpose_octaves=None, state=None):
        super().__init__(state=state)
        if state is None:
            self.name = name
            self.visible = visible
            self.muted = muted
            self.gain = gain
            self.pan = pan
            self.transpose_octaves = transpose_octaves

    def run(self, track):
        assert isinstance(track, Track)

        if self.name is not None:
            track.name = self.name

        if self.visible is not None:
            track.visible = self.visible

        if self.muted is not None:
            track.muted = self.muted
            track.mixer_node.set_control_value('muted', float(self.muted))

        if self.gain is not None:
            track.gain = self.gain
            track.mixer_node.set_control_value('gain', self.gain)

        if self.pan is not None:
            track.pan = self.pan
            track.mixer_node.set_control_value('pan', self.pan)

        if self.transpose_octaves is not None:
            track.transpose_octaves = self.transpose_octaves

commands.Command.register_command(UpdateTrackProperties)


class TrackConnector(object):
    def __init__(self, *, track, message_cb):
        self._track = track
        self.__message_cb = message_cb

        self.__initializing = True
        self.__initial_messages = []

    def init(self):
        assert self.__initializing
        self._init_internal()
        self.__initializing = False
        messages = self.__initial_messages
        self.__initial_messages = None
        return messages

    def _init_internal(self):
        raise NotImplementedError

    def _emit_message(self, msg):
        if self.__initializing:
            self.__initial_messages.append(msg)
        else:
            self.__message_cb(msg)

    def close(self):
        pass


class Track(model.Track, state.StateBase):
    def __init__(self, name=None, state=None):
        super().__init__(state)

        if state is None:
            self.name = name

    def create_track_connector(self, **kwargs):
        raise NotImplementedError

    @property
    def parent_mixer_name(self):
        return self.parent.mixer_name

    @property
    def parent_mixer_node(self):
        return self.parent.mixer_node

    # TODO: the following are common to MeasuredTrack and TrackGroup, but not really
    # generic for all track types.

    @property
    def mixer_name(self):
        return '%s-track-mixer' % self.id

    @property
    def mixer_node(self):
        if self.mixer_id is None:
            raise ValueError("No mixer node found.")

        return self.root.get_object(self.mixer_id)

    @property
    def relative_position_to_parent_mixer(self):
        return misc.Pos2F(-200, self.index * 100)

    @property
    def default_mixer_name(self):
        return "Track Mixer"

    def add_pipeline_nodes(self):
        parent_mixer_node = self.parent_mixer_node

        mixer_node = pipeline_graph.TrackMixerPipelineGraphNode(
            name=self.default_mixer_name,
            graph_pos=(
                parent_mixer_node.graph_pos
                + self.relative_position_to_parent_mixer),
            track=self)
        self.project.add_pipeline_graph_node(mixer_node)
        self.mixer_id = mixer_node.id

        conn = pipeline_graph.PipelineGraphConnection(
            mixer_node, 'out:left', parent_mixer_node, 'in:left')
        self.project.add_pipeline_graph_connection(conn)

        conn = pipeline_graph.PipelineGraphConnection(
            mixer_node, 'out:right', parent_mixer_node, 'in:right')
        self.project.add_pipeline_graph_connection(conn)

    def remove_pipeline_nodes(self):
        self.project.remove_pipeline_graph_node(self.mixer_node)
        self.mixer_id = None


class Measure(model.Measure, state.StateBase):
    @property
    def empty(self):
        return False


class MeasureReference(model.MeasureReference, state.StateBase):
    def __init__(self, measure_id=None, state=None):
        super().__init__(state)

        if state is None:
            self.measure_id = measure_id

state.StateBase.register_class(MeasureReference)


class PianoRollInterval(object):
    def __init__(self, begin, end, pitch, velocity):
        self.id = random.getrandbits(64)
        self.begin = begin
        self.end = end
        self.pitch = pitch
        self.velocity = velocity

    def __str__(self):
        return '<PianoRollInterval id=%016x begin=%s end=%s pitch=%s velocity=%s>' % (
            self.id, self.begin, self.end, self.pitch, self.velocity)
    __repr__ = __str__

    def create_add_message(self, node_id):
        return audioproc.ProcessorMessage(
            node_id=node_id,
            pianoroll_add_interval=audioproc.ProcessorMessage.PianoRollAddInterval(
                id=self.id,
                start_time=self.begin.to_proto(),
                end_time=self.end.to_proto(),
                pitch=self.pitch.midi_note,
                velocity=self.velocity))

    def create_remove_message(self, node_id):
        return audioproc.ProcessorMessage(
            node_id=node_id,
            pianoroll_remove_interval=audioproc.ProcessorMessage.PianoRollRemoveInterval(
                id=self.id))


class MeasuredTrackConnector(TrackConnector):
    def __init__(self, *, node_id, **kwargs):
        super().__init__(**kwargs)

        self._listeners = {}

        self.__node_id = node_id
        self.__measure_events = {}

    def _init_internal(self):
        time = audioproc.MusicalTime()
        for mref in self._track.measure_list:
            self.__add_measure(time, mref)
            time += mref.measure.duration

        self._listeners['measure_list'] = self._track.listeners.add(
            'measure_list', self.__measure_list_changed)
        self._add_track_listeners()

    def close(self):
        for listener in self._listeners.values():
            listener.remove()
        self._listeners.clear()

        super().close()

    def __add_event(self, event):
        self._emit_message(event.create_add_message(self.__node_id))

    def __remove_event(self, event):
        self._emit_message(event.create_remove_message(self.__node_id))

    def _add_track_listeners(self):
        pass

    def _add_measure_listeners(self, mref):
        pass

    def _remove_measure_listeners(self, mref):
        pass

    def _create_events(self, time, measure):
        raise NotImplementedError

    def _update_measure(self, time, mref):
        assert isinstance(mref, MeasureReference)
        events = self.__measure_events[mref.id]
        for event in events:
            self.__remove_event(event)
        events.clear()
        for event in self._create_events(time, mref.measure):
            self.__add_event(event)
            events.append(event)

    def _update_measure_range(self, begin, end):
        time = audioproc.MusicalTime()
        for mref in self._track.measure_list:
            if mref.index >= end:
                break

            if mref.index >= begin:
                self._update_measure(time, mref)

            time += mref.measure.duration

    def __measure_list_changed(self, change):
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

    def __add_measure(self, time, mref):
        assert isinstance(mref, MeasureReference)
        assert mref.id not in self.__measure_events

        events = self.__measure_events[mref.id] = []
        for event in self._create_events(time, mref.measure):
            self.__add_event(event)
            events.append(event)

        self._listeners['measure:%s:ref' % mref.id] = mref.listeners.add(
            'measure_id', lambda _: self.__measure_id_changed(mref))
        self._add_measure_listeners(mref)

    def __remove_measure(self, mref):
        assert isinstance(mref, MeasureReference)

        self._remove_measure_listeners(mref)
        self._listeners.pop('measure:%s:ref' % mref.id).remove()

        for event in self.__measure_events.pop(mref.id):
            self.__remove_event(event)

    def __measure_id_changed(self, mref):
        self._remove_measure_listeners(mref)
        self._listeners.pop('measure:%s:ref' % mref.id).remove()

        self._listeners['measure:%s:ref' % mref.id] = mref.listeners.add(
            'measure_id', lambda _: self.__measure_id_changed(mref))
        self._add_measure_listeners(mref)

        self._update_measure_range(mref.index, mref.index + 1)


class MeasuredTrack(model.MeasuredTrack, Track):
    measure_cls = None

    def __init__(self, state=None, **kwargs):
        super().__init__(state=state, **kwargs)

        if state is None:
            pass

        self.__listeners = {}

        for mref in self.measure_list:
            self.__add_measure(mref)

        self.listeners.add('measure_list', self.__measure_list_changed)

    def __measure_list_changed(self, change):
        if isinstance(change, core.PropertyListInsert):
            self.__add_measure(change.new_value)
        elif isinstance(change, core.PropertyListDelete):
            self.__remove_measure(change.old_value)
        else:
            raise TypeError("Unsupported change type %s" % type(change))

    def __add_measure(self, mref):
        self.__listeners['measure:%s:ref' % mref.id] = mref.listeners.add(
            'measure_id', lambda *_: self.__measure_id_changed(mref))
        self.listeners.call('duration_changed')

    def __remove_measure(self, mref):
        self.__listeners.pop('measure:%s:ref' % mref.id).remove()
        self.listeners.call('duration_changed')

    def __measure_id_changed(self, mref):
        self.listeners.call('duration_changed')

    def append_measure(self):
        self.insert_measure(-1)

    def insert_measure(self, idx):
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

    def garbage_collect_measures(self):
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

    def remove_measure(self, idx):
        del self.measure_list[idx]
        self.garbage_collect_measures()

    def create_empty_measure(self, ref):  # pylint: disable=unused-argument
        return self.measure_cls()  # pylint: disable=not-callable
