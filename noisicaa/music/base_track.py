#!/usr/bin/python3

import logging

from noisicaa.bindings import lv2
from noisicaa import audioproc
from noisicaa import core

from . import model
from . import state
from . import commands
from . import mutations
from . import pipeline_graph
from . import misc
from . import time
from . import event_set
from . import time_mapper

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
        assert new_parent.is_child_of(track.sheet)
        assert isinstance(new_parent, model.TrackGroup)

        assert 0 <= self.index <= len(new_parent.tracks)

        del track.parent.tracks[track.index]
        new_parent.tracks.insert(self.index, track)

commands.Command.register_command(ReparentTrack)


class UpdateTrackProperties(commands.Command):
    name = core.Property(str, allow_none=True)
    visible = core.Property(bool, allow_none=True)
    muted = core.Property(bool, allow_none=True)
    volume = core.Property(float, allow_none=True)

    # TODO: this only applies to ScoreTrack... use separate command for
    #   class specific properties?
    transpose_octaves = core.Property(int, allow_none=True)

    def __init__(self, name=None, visible=None, muted=None, volume=None,
                 transpose_octaves=None, state=None):
        super().__init__(state=state)
        if state is None:
            self.name = name
            self.visible = visible
            self.muted = muted
            self.volume = volume
            self.transpose_octaves = transpose_octaves

    def run(self, track):
        assert isinstance(track, Track)

        if self.name is not None:
            track.name = self.name

        if self.visible is not None:
            track.visible = self.visible

        if self.muted is not None:
            track.muted = self.muted
            track.sheet.handle_pipeline_mutation(
                mutations.SetPortProperty(
                    track.mixer_name, 'out', muted=track.muted))

        if self.volume is not None:
            track.volume = self.volume
            track.sheet.handle_pipeline_mutation(
                mutations.SetPortProperty(
                    track.mixer_name, 'out', volume=track.volume))

        if self.transpose_octaves is not None:
            track.transpose_octaves = self.transpose_octaves

commands.Command.register_command(UpdateTrackProperties)


class Track(model.Track, state.StateBase):
    def __init__(self, name=None, state=None):
        super().__init__(state)

        if state is None:
            self.name = name

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
        self.sheet.add_pipeline_graph_node(mixer_node)
        self.mixer_id = mixer_node.id

        conn = pipeline_graph.PipelineGraphConnection(
            mixer_node, 'out:left', parent_mixer_node, 'in:left')
        self.sheet.add_pipeline_graph_connection(conn)

        conn = pipeline_graph.PipelineGraphConnection(
            mixer_node, 'out:right', parent_mixer_node, 'in:right')
        self.sheet.add_pipeline_graph_connection(conn)

    def remove_pipeline_nodes(self):
        self.sheet.remove_pipeline_graph_node(self.mixer_node)
        self.mixer_id = None


class Measure(model.Measure, state.StateBase):
    def __init__(self, state=None):
        super().__init__(state)

    @property
    def empty(self):
        return False


class MeasureReference(model.MeasureReference, state.StateBase):
    def __init__(self, measure_id=None, state=None):
        super().__init__(state)

        if state is None:
            self.measure_id = measure_id

state.StateBase.register_class(MeasureReference)


class EntitySource(object):
    def __init__(self, track):
        self._track = track
        self._sheet = track.sheet

    def close(self):
        pass

    def get_entities(self, entities, start_pos, end_pos, frame_sample_pos):
        raise NotImplementedError


class EventSetEntitySource(EntitySource):
    def __init__(self, track):
        super().__init__(track)
        self.__event_set = event_set.EventSet()
        self.__connector = self._create_connector(track, self.__event_set)
        self.__time_mapper = time_mapper.TimeMapper(track.sheet)

    def _create_connector(self, track, event_set):
        raise NotImplementedError

    def close(self):
        self.__connector.close()
        super().close()

    def get_entities(self, entities, start_sample_pos, end_sample_pos, frame_sample_pos):
        start_timepos = self.__time_mapper.sample2timepos(start_sample_pos)
        end_timepos = self.__time_mapper.sample2timepos(end_sample_pos)
        entity_id = 'track:%s' % self._track.id

        buf = bytearray(10240)
        forge = lv2.AtomForge(lv2.static_mapper)
        forge.set_buffer(buf, len(buf))

        with forge.sequence():
            try:
                entity = entities[entity_id]
            except KeyError:
                pass
            else:
                # Copy events from existing entity.
                assert entity.type == audioproc.Entity.Type.atom

                for event in lv2.wrap_atom(lv2.static_mapper, entity.data).events:
                    atom = event.atom
                    forge.write_atom_event(
                        event.frames,
                        atom.type_urid, atom.data, atom.size)

            for event in sorted(self.__event_set.get_intervals(start_timepos, end_timepos)):
                if event.begin >= start_timepos:
                    sample_pos = self.__time_mapper.timepos2sample(event.begin)
                    assert start_sample_pos <= sample_pos < end_sample_pos
                    forge.write_midi_event(
                        sample_pos - start_sample_pos + frame_sample_pos,
                        bytes([0b10010000, event.pitch.midi_note, event.velocity]),
                        3)

                if event.end < end_timepos:
                    sample_pos = self.__time_mapper.timepos2sample(event.end)
                    assert start_sample_pos <= sample_pos < end_sample_pos
                    forge.write_midi_event(
                        sample_pos - start_sample_pos + frame_sample_pos,
                        bytes([0b10000000, event.pitch.midi_note, 0]),
                        3)

        entity = audioproc.Entity.new_message()
        entity.id = entity_id
        entity.type = audioproc.Entity.Type.atom
        entity.size = len(buf)
        entity.data = bytes(buf)

        entities[entity_id] = entity


class MeasuredEventSetConnector(object):
    def __init__(self, track, event_set):
        self._track = track
        self._listeners = {}

        self.__event_set = event_set
        self.__measure_events = {}

        timepos = time.Duration()
        for mref in self._track.measure_list:
            self.__add_measure(timepos, mref)
            timepos += mref.measure.duration

        self._listeners['measure_list'] = self._track.listeners.add(
            'measure_list', self.__measure_list_changed)
        self._add_track_listeners()

    def close(self):
        for listener in self._listeners.values():
            listener.remove()
        self._listeners.clear()

    def _add_track_listeners(self):
        pass

    def _add_measure_listeners(self, mref):
        pass

    def _remove_measure_listeners(self, mref):
        pass

    def _create_events(self, timepos, measure):
        raise NotImplementedError

    def _update_measure(self, timepos, mref):
        assert isinstance(mref, MeasureReference)
        events = self.__measure_events[mref.id]
        for event in events:
            self.__event_set.remove(event)
        events.clear()
        for event in self._create_events(timepos, mref.measure):
            self.__event_set.add(event)
            events.append(event)

    def _update_measure_range(self, begin, end):
        timepos = time.Duration()
        for mref in self._track.measure_list:
            if mref.index >= end:
                break

            if mref.index >= begin:
                self._update_measure(timepos, mref)

            timepos += mref.measure.duration

    def __measure_list_changed(self, change):
        if isinstance(change, core.PropertyListInsert):
            timepos = time.Duration()
            for mref in self._track.measure_list:
                if mref.index == change.new_value.index:
                    assert mref is change.new_value
                    self.__add_measure(timepos, mref)
                elif mref.index > change.new_value.index:
                    self._update_measure(timepos, mref)

                timepos += mref.measure.duration

        elif isinstance(change, core.PropertyListDelete):
            mref = change.old_value
            self.__remove_measure(mref)
        else:
            raise TypeError(
                "Unsupported change type %s" % type(change))

    def __add_measure(self, timepos, mref):
        assert isinstance(mref, MeasureReference)
        assert mref.id not in self.__measure_events

        events = self.__measure_events[mref.id] = []
        for event in self._create_events(timepos, mref.measure):
            self.__event_set.add(event)
            events.append(event)

        self._listeners['measure:%s:ref' % mref.id] = mref.listeners.add(
            'measure_id', lambda _: self.__measure_id_changed(mref))
        self._add_measure_listeners(mref)

    def __remove_measure(self, mref):
        assert isinstance(mref, MeasureReference)

        self._remove_measure_listeners(mref)
        self._listeners.pop('measure:%s:ref' % mref.id).remove()

        for event in self.__measure_events.pop(mref.id):
            self.__event_set.remove(event)

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
