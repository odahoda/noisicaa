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

import base64
import email.parser
import email.policy
import email.message
import itertools
import logging
import os.path
import time
import json
import textwrap

from noisicaa import core
from noisicaa.core import storage
from noisicaa import audioproc

from .pitch import Pitch
from .clef import Clef
from .key_signature import KeySignature
from .time_signature import TimeSignature
from . import base_track
from . import beat_track
from . import commands
from . import control_track
from . import misc
from . import model
from . import pipeline_graph
from . import property_track
from . import sample_track
from . import score_track
from . import state
from . import track_group

logger = logging.getLogger(__name__)


class UpdateProjectProperties(commands.Command):
    bpm = core.Property(int, allow_none=True)

    def __init__(self, bpm=None, state=None):
        super().__init__(state=state)
        if state is None:
            self.bpm = bpm

    def run(self, project):
        assert isinstance(project, BaseProject)

        if self.bpm is not None:
            project.bpm = self.bpm

commands.Command.register_command(UpdateProjectProperties)


class AddTrack(commands.Command):
    track_type = core.Property(str)
    parent_group_id = core.Property(str)
    insert_index = core.Property(int)

    def __init__(self, track_type=None, parent_group_id=None, insert_index=-1, state=None):
        super().__init__(state=state)
        if state is None:
            self.track_type = track_type
            self.parent_group_id = parent_group_id
            self.insert_index = insert_index

    def run(self, project):
        assert isinstance(project, BaseProject)

        parent_group = project.get_object(self.parent_group_id)
        assert parent_group.is_child_of(project)
        assert isinstance(parent_group, track_group.TrackGroup)

        if self.insert_index == -1:
            insert_index = len(parent_group.tracks)
        else:
            insert_index = self.insert_index
            assert 0 <= insert_index <= len(parent_group.tracks)

        track_name = "Track %d" % (len(parent_group.tracks) + 1)
        track_cls_map = {
            'score': score_track.ScoreTrack,
            'beat': beat_track.BeatTrack,
            'control': control_track.ControlTrack,
            'sample': sample_track.SampleTrack,
            'group': track_group.TrackGroup,
        }
        track_cls = track_cls_map[self.track_type]

        kwargs = {}
        if issubclass(track_cls, model.MeasuredTrack):
            num_measures = 1
            for track in parent_group.walk_tracks():
                if isinstance(track, model.MeasuredTrack):
                    num_measures = max(num_measures, len(track.measure_list))
            kwargs['num_measures'] = num_measures

        track = track_cls(name=track_name, **kwargs)

        project.add_track(parent_group, insert_index, track)

        return insert_index

commands.Command.register_command(AddTrack)


class RemoveTrack(commands.Command):
    track_id = core.Property(str)

    def __init__(self, track_id=None, state=None):
        super().__init__(state=state)
        if state is None:
            self.track_id = track_id

    def run(self, project):
        assert isinstance(project, BaseProject)

        track = project.get_object(self.track_id)
        assert track.is_child_of(project)
        parent_group = track.parent

        project.remove_track(parent_group, track)

commands.Command.register_command(RemoveTrack)


class InsertMeasure(commands.Command):
    tracks = core.ListProperty(str)
    pos = core.Property(int)

    def __init__(self, tracks=None, pos=None, state=None):
        super().__init__(state=state)
        if state is None:
            self.tracks.extend(tracks)
            self.pos = pos

    def run(self, project):
        assert isinstance(project, BaseProject)

        if not self.tracks:
            project.property_track.insert_measure(self.pos)
        else:
            project.property_track.append_measure()

        for track in project.master_group.walk_tracks():
            if not isinstance(track, model.MeasuredTrack):
                continue

            if not self.tracks or track.id in self.tracks:
                track.insert_measure(self.pos)
            else:
                track.append_measure()

commands.Command.register_command(InsertMeasure)


class RemoveMeasure(commands.Command):
    tracks = core.ListProperty(int)
    pos = core.Property(int)

    def __init__(self, tracks=None, pos=None, state=None):
        super().__init__(state=state)
        if state is None:
            self.tracks.extend(tracks)
            self.pos = pos

    def run(self, project):
        assert isinstance(project, BaseProject)

        if not self.tracks:
            project.property_track.remove_measure(self.pos)

        for idx, track in enumerate(project.master_group.tracks):
            if not self.tracks or idx in self.tracks:
                track.remove_measure(self.pos)
                if self.tracks:
                    track.append_measure()

commands.Command.register_command(RemoveMeasure)


class SetNumMeasures(commands.Command):
    num_measures = core.Property(int)

    def __init__(self, num_measures=None, state=None):
        super().__init__(state=state)
        if state is None:
            self.num_measures = num_measures

    def run(self, project):
        assert isinstance(project, BaseProject)

        for track in project.all_tracks:
            if not isinstance(track, model.MeasuredTrack):
                continue

            while len(track.measure_list) < self.num_measures:
                track.append_measure()

            while len(track.measure_list) > self.num_measures:
                track.remove_measure(len(track.measure_list) - 1)

commands.Command.register_command(SetNumMeasures)


class ClearMeasures(commands.Command):
    measure_ids = core.ListProperty(str)

    def __init__(self, measure_ids=None, state=None):
        super().__init__(state=state)
        if state is None:
            self.measure_ids.extend(measure_ids)

    def run(self, project):
        assert isinstance(project, BaseProject)

        measure_references = [project.get_object(obj_id) for obj_id in self.measure_ids]
        assert all(isinstance(obj, base_track.MeasureReference) for obj in measure_references)

        affected_track_ids = set(obj.track.id for obj in measure_references)

        for mref in measure_references:
            track = mref.track
            measure = track.create_empty_measure(mref.measure)
            track.measure_heap.append(measure)
            mref.measure_id = measure.id

        for track_id in affected_track_ids:
            project.get_object(track_id).garbage_collect_measures()

commands.Command.register_command(ClearMeasures)


class PasteMeasures(commands.Command):
    mode = core.Property(str)
    src_objs = core.ListProperty(bytes)
    target_ids = core.ListProperty(str)

    def __init__(self, mode=None, src_objs=None, target_ids=None, state=None):
        super().__init__(state=state)
        if state is None:
            self.mode = mode
            self.src_objs.extend(src_objs)
            self.target_ids.extend(target_ids)

    def run(self, project):
        assert isinstance(project, BaseProject)

        src_measures = [project.deserialize_object(obj) for obj in self.src_objs]
        assert all(isinstance(obj, base_track.Measure) for obj in src_measures)

        target_measures = [project.get_object(obj_id) for obj_id in self.target_ids]
        assert all(isinstance(obj, base_track.MeasureReference) for obj in target_measures)

        affected_track_ids = set(obj.track.id for obj in target_measures)
        assert len(affected_track_ids) == 1

        if self.mode == 'link':
            for target, src in zip(target_measures, itertools.cycle(src_measures)):
                assert(any(src.id == m.id for m in target.track.measure_heap))
                target.measure_id = src.id

        elif self.mode == 'overwrite':
            measure_map = {}
            for target, src in zip(target_measures, itertools.cycle(src_measures)):
                try:
                    measure = measure_map[src.id]
                except KeyError:
                    measure = measure_map[src.id] = src.clone()
                    target.track.measure_heap.append(measure)

                target.measure_id = measure.id

        else:
            raise ValueError(self.mode)

        for track_id in affected_track_ids:
            project.get_object(track_id).garbage_collect_measures()

commands.Command.register_command(PasteMeasures)


class AddPipelineGraphNode(commands.Command):
    uri = core.Property(str)
    graph_pos = core.Property(misc.Pos2F)

    def __init__(self, uri=None, graph_pos=None, state=None):
        super().__init__(state=state)
        if state is None:
            self.uri = uri
            self.graph_pos = graph_pos

    def run(self, project):
        assert isinstance(project, BaseProject)

        node_desc = project.project.get_node_description(self.uri)

        node = pipeline_graph.PipelineGraphNode(
            name=node_desc.display_name,
            node_uri=self.uri,
            graph_pos=self.graph_pos)
        project.add_pipeline_graph_node(node)
        return node.id

commands.Command.register_command(AddPipelineGraphNode)


class RemovePipelineGraphNode(commands.Command):
    node_id = core.Property(str)

    def __init__(self, node_id=None, state=None):
        super().__init__(state=state)
        if state is None:
            self.node_id = node_id

    def run(self, project):
        assert isinstance(project, BaseProject)

        node = project.get_object(self.node_id)
        assert node.is_child_of(project)

        project.remove_pipeline_graph_node(node)

commands.Command.register_command(RemovePipelineGraphNode)


class AddPipelineGraphConnection(commands.Command):
    source_node_id = core.Property(str)
    source_port_name = core.Property(str)
    dest_node_id = core.Property(str)
    dest_port_name = core.Property(str)

    def __init__(
            self,
            source_node_id=None, source_port_name=None,
            dest_node_id=None, dest_port_name=None,
            state=None):
        super().__init__(state=state)
        if state is None:
            self.source_node_id = source_node_id
            self.source_port_name = source_port_name
            self.dest_node_id = dest_node_id
            self.dest_port_name = dest_port_name

    def run(self, project):
        assert isinstance(project, BaseProject)

        source_node = project.get_object(self.source_node_id)
        assert source_node.is_child_of(project)
        dest_node = project.get_object(self.dest_node_id)
        assert dest_node.is_child_of(project)

        connection = pipeline_graph.PipelineGraphConnection(
            source_node=source_node, source_port=self.source_port_name,
            dest_node=dest_node, dest_port=self.dest_port_name)
        project.add_pipeline_graph_connection(connection)
        return connection.id

commands.Command.register_command(AddPipelineGraphConnection)


class RemovePipelineGraphConnection(commands.Command):
    connection_id = core.Property(str)

    def __init__(self, connection_id=None, state=None):
        super().__init__(state=state)
        if state is None:
            self.connection_id = connection_id

    def run(self, project):
        assert isinstance(project, BaseProject)

        connection = project.get_object(self.connection_id)
        assert connection.is_child_of(project)

        project.remove_pipeline_graph_connection(connection)

commands.Command.register_command(RemovePipelineGraphConnection)


class Metadata(model.Metadata, state.StateBase):
    pass

state.StateBase.register_class(Metadata)


class JSONEncoder(json.JSONEncoder):
    def default(self, obj):  # pylint: disable=method-hidden
        if isinstance(obj, bytes):
            return {'__type__': 'bytes',
                    'value': base64.b85encode(obj).decode('ascii')}
        if isinstance(obj, audioproc.MusicalDuration):
            return {'__type__': 'MusicalDuration',
                    'value': [obj.numerator, obj.denominator]}
        if isinstance(obj, audioproc.MusicalTime):
            return {'__type__': 'MusicalTime',
                    'value': [obj.numerator, obj.denominator]}
        if isinstance(obj, Pitch):
            return {'__type__': 'Pitch',
                    'value': [obj.name]}
        if isinstance(obj, Clef):
            return {'__type__': 'Clef',
                    'value': [obj.value]}
        if isinstance(obj, KeySignature):
            return {'__type__': 'KeySignature',
                    'value': [obj.name]}
        if isinstance(obj, TimeSignature):
            return {'__type__': 'TimeSignature',
                    'value': [obj.upper, obj.lower]}
        if isinstance(obj, misc.Pos2F):
            return {'__type__': 'Pos2F',
                    'value': [obj.x, obj.y]}
        return super().default(obj)


class JSONDecoder(json.JSONDecoder):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, object_hook=self.object_hook, **kwargs)

    def object_hook(self, obj):  # pylint: disable=method-hidden
        objtype = obj.get('__type__', None)
        if objtype == 'bytes':
            return base64.b85decode(obj['value'])
        if objtype == 'MusicalDuration':
            return audioproc.MusicalDuration(*obj['value'])
        if objtype == 'MusicalTime':
            return audioproc.MusicalTime(*obj['value'])
        if objtype == 'Pitch':
            return Pitch(*obj['value'])
        if objtype == 'Clef':
            return Clef(*obj['value'])
        if objtype == 'KeySignature':
            return KeySignature(*obj['value'])
        if objtype == 'TimeSignature':
            return TimeSignature(*obj['value'])
        if objtype == 'Pos2F':
            return misc.Pos2F(*obj['value'])
        return obj


class BaseProject(model.Project, state.RootMixin, state.StateBase):
    SERIALIZED_CLASS_NAME = 'Project'

    def __init__(self, *, node_db=None, state=None):
        self.node_db = node_db

        super().__init__(state)
        if state is None:
            self.metadata = Metadata()
            self.master_group = track_group.MasterTrackGroup(name="Master")
            self.property_track = property_track.PropertyTrack(name="Time")

            audio_out_node = pipeline_graph.AudioOutPipelineGraphNode(
                name="Audio Out", graph_pos=misc.Pos2F(200, 0))
            self.add_pipeline_graph_node(audio_out_node)
            self.master_group.add_pipeline_nodes()

        self._duration = self.master_group.duration
        self.master_group.listeners.add('duration_changed', self._on_duration_changed)

    @property
    def duration(self):
        return self._duration

    def _on_duration_changed(self):
        old_duration = self._duration
        new_duration = self.master_group.duration
        if new_duration != self._duration:
            self._duration = new_duration
            self.listeners.call(
                'duration', core.PropertyValueChange('duration', old_duration, new_duration))

    def get_node_description(self, uri):
        return self.node_db.get_node_description(uri)

    def dispatch_command(self, obj_id, cmd):
        obj = self.get_object(obj_id)
        result = cmd.apply(obj)
        logger.info(
            "Executed command %s on %s (%d operations)",
            cmd, obj_id, len(cmd.log.ops))
        return result

    def equalize_tracks(self, remove_trailing_empty_measures=0):
        if len(self.master_group.tracks) < 1:
            return

        while remove_trailing_empty_measures > 0:
            max_length = max(
                len(track.measure_list) for track in self.all_tracks)
            if max_length < 2:
                break

            can_remove = True
            for track in self.all_tracks:
                if len(track.measure_list) < max_length:
                    continue
                if not track.measure_list[max_length - 1].measure.empty:
                    can_remove = False
            if not can_remove:
                break

            for track in self.all_tracks:
                if len(track.measure_list) < max_length:
                    continue
                track.remove_measure(max_length - 1)

            remove_trailing_empty_measures -= 1

        max_length = max(len(track.measure_list) for track in self.all_tracks)

        for track in self.all_tracks:
            while len(track.measure_list) < max_length:
                track.append_measure()

    def add_track(self, parent_group, insert_index, track):
        parent_group.tracks.insert(insert_index, track)
        track.add_pipeline_nodes()

    def remove_track(self, parent_group, track):
        track.remove_pipeline_nodes()
        del parent_group.tracks[track.index]

    def handle_pipeline_mutation(self, mutation):
        self.listeners.call('pipeline_mutations', mutation)

    @property
    def audio_out_node(self):
        for node in self.pipeline_graph_nodes:
            if isinstance(node, pipeline_graph.AudioOutPipelineGraphNode):
                return node

        raise ValueError("No audio out node found.")

    def add_pipeline_graph_node(self, node):
        self.pipeline_graph_nodes.append(node)
        node.add_to_pipeline()

    def remove_pipeline_graph_node(self, node):
        delete_connections = set()
        for cidx, connection in enumerate(
                self.pipeline_graph_connections):
            if connection.source_node is node:
                delete_connections.add(cidx)
            if connection.dest_node is node:
                delete_connections.add(cidx)
        for cidx in sorted(delete_connections, reverse=True):
            self.remove_pipeline_graph_connection(
                self.pipeline_graph_connections[cidx])

        node.remove_from_pipeline()
        del self.pipeline_graph_nodes[node.index]

    def add_pipeline_graph_connection(self, connection):
        self.pipeline_graph_connections.append(connection)
        connection.add_to_pipeline()

    def remove_pipeline_graph_connection(self, connection):
        connection.remove_from_pipeline()
        del self.pipeline_graph_connections[connection.index]

    def add_to_pipeline(self):
        for node in self.pipeline_graph_nodes:
            node.add_to_pipeline()
        for connection in self.pipeline_graph_connections:
            connection.add_to_pipeline()

    def remove_from_pipeline(self):
        for connection in self.pipeline_graph_connections:
            connection.remove_from_pipeline()
        for node in self.pipeline_graph_nodes:
            node.remove_from_pipeline()

    @classmethod
    def make_demo(cls, demo='basic', **kwargs):
        project = cls(**kwargs)
        project.bpm = 140

        master_mixer = project.master_group.mixer_node

        if demo == 'basic':
            while len(project.property_track.measure_list) < 5:
                project.property_track.append_measure()

            track1 = score_track.ScoreTrack(
                name="Track 1",
                instrument='sf2:/usr/share/sounds/sf2/FluidR3_GM.sf2?bank=0&preset=73',
                num_measures=5)
            project.add_track(project.master_group, 0, track1)

            track2 = score_track.ScoreTrack(
                name="Track 2",
                instrument='sf2:/usr/share/sounds/sf2/FluidR3_GM.sf2?bank=0&preset=0',
                num_measures=5)
            project.add_track(project.master_group, 1, track2)

            track1.measure_list[0].measure.notes.append(
                score_track.Note(pitches=[Pitch('C5')], base_duration=audioproc.MusicalDuration(1, 4)))
            track1.measure_list[0].measure.notes.append(
                score_track.Note(pitches=[Pitch('D5')], base_duration=audioproc.MusicalDuration(1, 4)))
            track1.measure_list[0].measure.notes.append(
                score_track.Note(pitches=[Pitch('E5')], base_duration=audioproc.MusicalDuration(1, 4)))
            track1.measure_list[0].measure.notes.append(
                score_track.Note(pitches=[Pitch('F5')], base_duration=audioproc.MusicalDuration(1, 4)))

            track1.measure_list[1].measure.notes.append(
                score_track.Note(pitches=[Pitch('C5')], base_duration=audioproc.MusicalDuration(1, 2)))
            track1.measure_list[1].measure.notes.append(
                score_track.Note(pitches=[Pitch('F5')], base_duration=audioproc.MusicalDuration(1, 8)))
            track1.measure_list[1].measure.notes.append(
                score_track.Note(pitches=[Pitch('E5')], base_duration=audioproc.MusicalDuration(1, 8)))
            track1.measure_list[1].measure.notes.append(
                score_track.Note(pitches=[Pitch('D5')], base_duration=audioproc.MusicalDuration(1, 4)))

            track1.measure_list[2].measure.notes.append(
                score_track.Note(pitches=[Pitch('C5')], base_duration=audioproc.MusicalDuration(1, 4)))
            track1.measure_list[2].measure.notes.append(
                score_track.Note(pitches=[Pitch('D5')], base_duration=audioproc.MusicalDuration(1, 4)))
            track1.measure_list[2].measure.notes.append(
                score_track.Note(pitches=[Pitch('E5')], base_duration=audioproc.MusicalDuration(1, 4)))
            track1.measure_list[2].measure.notes.append(
                score_track.Note(pitches=[Pitch('F5')], base_duration=audioproc.MusicalDuration(1, 4)))

            track1.measure_list[3].measure.notes.append(
                score_track.Note(pitches=[Pitch('C5')], base_duration=audioproc.MusicalDuration(1, 2)))
            track1.measure_list[3].measure.notes.append(
                score_track.Note(pitches=[Pitch('F5')], base_duration=audioproc.MusicalDuration(1, 8)))
            track1.measure_list[3].measure.notes.append(
                score_track.Note(pitches=[Pitch('E5')], base_duration=audioproc.MusicalDuration(1, 8)))
            track1.measure_list[3].measure.notes.append(
                score_track.Note(pitches=[Pitch('D5')], base_duration=audioproc.MusicalDuration(1, 4)))

            track1.measure_list[4].measure.notes.append(
                score_track.Note(pitches=[Pitch('C5')], base_duration=audioproc.MusicalDuration(1, 1)))


            track2.measure_list[0].measure.notes.append(
                score_track.Note(pitches=[Pitch('C4'), Pitch('E3'), Pitch('G3')],
                     base_duration=audioproc.MusicalDuration(1, 1)))
            track2.measure_list[1].measure.notes.append(
                score_track.Note(pitches=[Pitch('F3'), Pitch('A4'), Pitch('C4')],
                     base_duration=audioproc.MusicalDuration(1, 1)))

            track2.measure_list[2].measure.notes.append(
                score_track.Note(pitches=[Pitch('A3'), Pitch('C4'), Pitch('E4')],
                     base_duration=audioproc.MusicalDuration(1, 1)))
            track2.measure_list[3].measure.notes.append(
                score_track.Note(pitches=[Pitch('C4'), Pitch('E3'), Pitch('G3')],
                     base_duration=audioproc.MusicalDuration(1, 1)))

            track2.measure_list[4].measure.notes.append(
                score_track.Note(pitches=[Pitch('C4'), Pitch('E3'), Pitch('G3')],
                     base_duration=audioproc.MusicalDuration(1, 1)))

        elif demo == 'complex':
            while len(project.property_track.measure_list) < 4:
                project.property_track.append_measure()

            track1 = score_track.ScoreTrack(
                name="Track 1",
                instrument='sf2:/usr/share/sounds/sf2/FluidR3_GM.sf2?bank=0&preset=0',
                num_measures=4)
            project.add_track(project.master_group, 0, track1)

            track1_mixer = track1.mixer_node

            for connection in project.pipeline_graph_connections:
                if (connection.source_node.id == track1_mixer.id
                    and connection.source_port == 'out:left'):
                    assert connection.dest_node.id == master_mixer.id
                    assert connection.dest_port == 'in:left'
                    project.remove_pipeline_graph_connection(connection)
                    break
            else:
                raise AssertionError("Connection not found.")

            for connection in project.pipeline_graph_connections:
                if (connection.source_node.id == track1_mixer.id
                    and connection.source_port == 'out:right'):
                    assert connection.dest_node.id == master_mixer.id
                    assert connection.dest_port == 'in:right'
                    project.remove_pipeline_graph_connection(connection)
                    break
            else:
                raise AssertionError("Connection not found.")

            eq_node_uri = 'ladspa://dj_eq_1901.so/dj_eq'
            eq_node = pipeline_graph.PipelineGraphNode(
                name='EQ',
                node_uri=eq_node_uri)
            project.add_pipeline_graph_node(eq_node)
            eq_node.set_control_value('Lo gain (dB)', -40.0)
            eq_node.set_control_value('Mid gain (dB)', 0.0)
            eq_node.set_control_value('Hi gain (dB)', 5.0)

            filter_node_uri = 'builtin://custom_csound'
            filter_node = pipeline_graph.PipelineGraphNode(
                name='Filter',
                node_uri=filter_node_uri)
            filter_node.set_parameter(
                'csound_orchestra',
                textwrap.dedent('''\
                    instr 2
                        printk(0.5, k(gaCtrl))
                        gaOutLeft = butterlp(gaInLeft, 200 + 2000 * gaCtrl)
                        gaOutRight = butterlp(gaInRight, 200 + 2000 * gaCtrl)
                    endin
                '''))
            project.add_pipeline_graph_node(filter_node)

            project.add_pipeline_graph_connection(
                pipeline_graph.PipelineGraphConnection(
                    source_node=track1_mixer, source_port='out:left',
                    dest_node=eq_node, dest_port='Input L'))
            project.add_pipeline_graph_connection(
                pipeline_graph.PipelineGraphConnection(
                    source_node=track1_mixer, source_port='out:right',
                    dest_node=eq_node, dest_port='Input R'))

            project.add_pipeline_graph_connection(
                pipeline_graph.PipelineGraphConnection(
                    source_node=eq_node, source_port='Output L',
                    dest_node=filter_node, dest_port='in:left'))
            project.add_pipeline_graph_connection(
                pipeline_graph.PipelineGraphConnection(
                    source_node=eq_node, source_port='Output R',
                    dest_node=filter_node, dest_port='in:right'))

            project.add_pipeline_graph_connection(
                pipeline_graph.PipelineGraphConnection(
                    source_node=filter_node, source_port='out:left',
                    dest_node=master_mixer, dest_port='in:left'))
            project.add_pipeline_graph_connection(
                pipeline_graph.PipelineGraphConnection(
                    source_node=filter_node, source_port='out:right',
                    dest_node=master_mixer, dest_port='in:right'))

            for i in range(4):
                track1.measure_list[i].measure.notes.append(
                    score_track.Note(pitches=[Pitch('C4')], base_duration=audioproc.MusicalDuration(1, 4)))
                track1.measure_list[i].measure.notes.append(
                    score_track.Note(pitches=[Pitch('E4')], base_duration=audioproc.MusicalDuration(1, 4)))
                track1.measure_list[i].measure.notes.append(
                    score_track.Note(pitches=[Pitch('G4')], base_duration=audioproc.MusicalDuration(1, 2)))

            track2 = beat_track.BeatTrack(
                name="Track 2",
                instrument='sample:' + os.path.abspath(os.path.join(
                    os.path.dirname(__file__), 'testdata', 'kick-gettinglaid.wav')),
                num_measures=4)
            track2.pitch = Pitch('C4')
            project.add_track(project.master_group, 1, track2)

            track2_mixer = track2.mixer_node

            for connection in project.pipeline_graph_connections:
                if (connection.source_node.id == track2_mixer.id
                    and connection.source_port == 'out:left'):
                    assert connection.dest_node.id == master_mixer.id
                    assert connection.dest_port == 'in:left'
                    project.remove_pipeline_graph_connection(connection)
                    break
            else:
                raise AssertionError("Connection not found.")

            for connection in project.pipeline_graph_connections:
                if (connection.source_node.id == track2_mixer.id
                    and connection.source_port == 'out:right'):
                    assert connection.dest_node.id == master_mixer.id
                    assert connection.dest_port == 'in:right'
                    project.remove_pipeline_graph_connection(connection)
                    break
            else:
                raise AssertionError("Connection not found.")

            delay_node_uri = 'http://drobilla.net/plugins/mda/Delay'
            delay_node = pipeline_graph.PipelineGraphNode(
                name='Delay',
                node_uri=delay_node_uri)
            project.add_pipeline_graph_node(delay_node)
            delay_node.set_control_value('l_delay', 0.3)
            delay_node.set_control_value('r_delay', 0.31)

            reverb_node_uri = 'builtin://csound/reverb'
            reverb_node = pipeline_graph.PipelineGraphNode(
                name='Reverb',
                node_uri=reverb_node_uri)
            project.add_pipeline_graph_node(reverb_node)

            project.add_pipeline_graph_connection(
                pipeline_graph.PipelineGraphConnection(
                    source_node=track2_mixer, source_port='out:left',
                    dest_node=delay_node, dest_port='left_in'))
            project.add_pipeline_graph_connection(
                pipeline_graph.PipelineGraphConnection(
                    source_node=track2_mixer, source_port='out:right',
                    dest_node=delay_node, dest_port='right_in'))

            project.add_pipeline_graph_connection(
                pipeline_graph.PipelineGraphConnection(
                    source_node=delay_node, source_port='left_out',
                    dest_node=reverb_node, dest_port='in:left'))
            project.add_pipeline_graph_connection(
                pipeline_graph.PipelineGraphConnection(
                    source_node=delay_node, source_port='right_out',
                    dest_node=reverb_node, dest_port='in:right'))

            project.add_pipeline_graph_connection(
                pipeline_graph.PipelineGraphConnection(
                    source_node=reverb_node, source_port='out:left',
                    dest_node=master_mixer, dest_port='in:left'))
            project.add_pipeline_graph_connection(
                pipeline_graph.PipelineGraphConnection(
                    source_node=reverb_node, source_port='out:right',
                    dest_node=master_mixer, dest_port='in:right'))

            for i in range(4):
                track2.measure_list[i].measure.beats.append(
                    beat_track.Beat(time=audioproc.MusicalDuration(0, 4), velocity=100))
                track2.measure_list[i].measure.beats.append(
                    beat_track.Beat(time=audioproc.MusicalDuration(1, 4), velocity=80))
                track2.measure_list[i].measure.beats.append(
                    beat_track.Beat(time=audioproc.MusicalDuration(2, 4), velocity=60))
                track2.measure_list[i].measure.beats.append(
                    beat_track.Beat(time=audioproc.MusicalDuration(3, 4), velocity=40))

            track3 = sample_track.SampleTrack(
                name="Track 3")
            project.add_track(project.master_group, 2, track3)

            smpl = sample_track.Sample(
                path=os.path.abspath(os.path.join(
                    os.path.dirname(__file__), 'testdata', 'future-thunder1.wav')))
            project.samples.append(smpl)

            track3.samples.append(
                sample_track.SampleRef(time=audioproc.MusicalTime(2, 4), sample_id=smpl.id))
            track3.samples.append(
                sample_track.SampleRef(time=audioproc.MusicalTime(14, 4), sample_id=smpl.id))

            track4 = control_track.ControlTrack(
                name="Track 4")
            project.add_track(project.master_group, 3, track4)

            track4.points.append(
                control_track.ControlPoint(time=audioproc.MusicalTime(0, 4), value=1.0))
            track4.points.append(
                control_track.ControlPoint(time=audioproc.MusicalTime(4, 4), value=0.0))
            track4.points.append(
                control_track.ControlPoint(time=audioproc.MusicalTime(8, 4), value=1.0))

            project.add_pipeline_graph_connection(
                pipeline_graph.PipelineGraphConnection(
                    source_node=track4.generator_node, source_port='out',
                    dest_node=filter_node, dest_port='ctrl'))

        return project


class Project(BaseProject):
    VERSION = 1
    SUPPORTED_VERSIONS = [1]

    def __init__(self, state=None, **kwargs):
        super().__init__(state=state, **kwargs)

        self.storage = None

    @property
    def closed(self):
        return self.storage is None

    @property
    def path(self):
        if self.storage:
            return self.storage.path
        return None

    @property
    def data_dir(self):
        if self.storage:
            return self.storage.data_dir
        return None

    def open(self, path):
        assert self.storage is None

        self.storage = storage.ProjectStorage()
        self.storage.open(path)

        checkpoint_number, actions = self.storage.get_restore_info()

        serialized_checkpoint = self.storage.get_checkpoint(
            checkpoint_number)

        self.load_from_checkpoint(serialized_checkpoint)
        for action, log_number in actions:
            cmd_data = self.storage.get_log_entry(log_number)
            cmd, obj_id = self.deserialize_command(cmd_data)
            logger.info(
                "Replay action %s of command %s on %s (%d operations)",
                action, cmd, obj_id, len(cmd.log.ops))
            obj = self.get_object(obj_id)

            if action == storage.ACTION_FORWARD:
                cmd.redo(obj)
            elif action == storage.ACTION_BACKWARD:
                cmd.undo(obj)
            else:
                raise ValueError("Unsupported action %s" % action)

    def create(self, path):
        assert self.storage is None

        self.storage = storage.ProjectStorage.create(path)

        # Write initial checkpoint of an empty project.
        self.create_checkpoint()

    def close(self):
        if self.storage is not None:
            self.storage.close()
            self.storage = None

        self.listeners.clear()
        self.reset_state()

    def load_from_checkpoint(self, checkpoint_data):
        parser = email.parser.BytesParser()
        message = parser.parsebytes(checkpoint_data)

        version = int(message['Version'])
        if version not in self.SUPPORTED_VERSIONS:
            raise storage.UnsupportedFileVersionError()

        if message.get_content_type() != 'application/json':
            raise storage.CorruptedProjectError(
                "Unexpected content type %s" % message.get_content_type())

        self.deserialize_object_into(message.get_payload(), self)
        self.init_references()

        def validate_node(root, parent, node):
            assert node.parent is parent, (node.parent, parent)
            assert node.root is root, (node.root, root)

            for c in node.list_children():
                validate_node(root, node, c)

        validate_node(self, None, self)

        # This is a bit silly. The master_group object was replaces, so the listener that
        # was created in BaseProject.__init__ listens on the wrong object.
        # So we have to recreate it here.
        # Would be better, if this was a classmethod, which creates the Project object directly
        # from the checkpoint data, so the master_group object as seen in BaseProject.__init__
        # remains unchanged for the lifetime of the project.
        self._duration = self.master_group.duration
        self.master_group.listeners.add('duration_changed', self._on_duration_changed)

    def create_checkpoint(self):
        policy = email.policy.compat32.clone(
            linesep='\n',
            max_line_length=0,
            cte_type='8bit',
            raise_on_defect=True)
        message = email.message.Message(policy)

        message['Version'] = str(self.VERSION)
        message['Content-Type'] = 'application/json; charset=utf-8'

        message.set_payload(self.serialize_object(self))

        checkpoint_data = message.as_bytes()
        self.storage.add_checkpoint(checkpoint_data)

    def serialize_object(self, obj):
        state = obj.serialize()
        dump = json.dumps(state, ensure_ascii=False, indent='  ', sort_keys=True, cls=JSONEncoder)
        return dump.encode('utf-8')

    def deserialize_object_into(self, data, target):
        if isinstance(data, bytes):
            data = data.decode('utf-8')
        state = json.loads(data, cls=JSONDecoder)
        target.deserialize(state)

    def deserialize_object(self, data):
        if isinstance(data, bytes):
            data = data.decode('utf-8')
        state = json.loads(data, cls=JSONDecoder)
        cls_name = state['__class__']
        cls = self.cls_map[cls_name]
        obj = cls(state=state)
        return obj

    def serialize_command(self, cmd, target_id, now):
        state = cmd.serialize()
        dump = json.dumps(state, ensure_ascii=False, indent='  ', sort_keys=True, cls=JSONEncoder)
        serialized = dump.encode('utf-8')

        policy = email.policy.compat32.clone(
            linesep='\n',
            max_line_length=0,
            cte_type='8bit',
            raise_on_defect=True)
        message = email.message.Message(policy)
        message['Version'] = str(self.VERSION)
        message['Content-Type'] = 'application/json; charset=utf-8'
        message['Target'] = target_id
        message['Time'] = time.ctime(now)
        message['Timestamp'] = '%d' % now
        message.set_payload(serialized)

        return message.as_bytes()

    def deserialize_command(self, cmd_data):
        parser = email.parser.BytesParser()
        message = parser.parsebytes(cmd_data)

        target_id = message['Target']
        cmd_state = json.loads(message.get_payload(), cls=JSONDecoder)
        cmd = commands.Command.create_from_state(cmd_state)

        return cmd, target_id

    def dispatch_command(self, obj_id, cmd):
        if self.closed:
            raise RuntimeError(
                "Command %s executed on closed project." % cmd)

        now = time.time()
        result = super().dispatch_command(obj_id, cmd)

        if not cmd.is_noop:
            self.storage.append_log_entry(
                self.serialize_command(cmd, obj_id, now))

            if self.storage.logs_since_last_checkpoint > 1000:
                self.create_checkpoint()

        return result

    def undo(self):
        if self.closed:
            raise RuntimeError("Undo executed on closed project.")

        if self.storage.can_undo:
            action, cmd_data = self.storage.get_log_entry_to_undo()
            cmd, obj_id = self.deserialize_command(cmd_data)
            logger.info(
                "Undo command %s on %s (%d operations)",
                cmd, obj_id, len(cmd.log.ops))
            obj = self.get_object(obj_id)

            if action == storage.ACTION_FORWARD:
                cmd.redo(obj)
            elif action == storage.ACTION_BACKWARD:
                cmd.undo(obj)
            else:
                raise ValueError("Unsupported action %s" % action)

            self.storage.undo()

    def redo(self):
        if self.closed:
            raise RuntimeError("Redo executed on closed project.")

        if self.storage.can_redo:
            action, cmd_data = self.storage.get_log_entry_to_redo()
            cmd, obj_id = self.deserialize_command(cmd_data)
            logger.info(
                "Redo command %s on %s (%d operations)",
                cmd, obj_id, len(cmd.log.ops))
            obj = self.get_object(obj_id)

            if action == storage.ACTION_FORWARD:
                cmd.redo(obj)
            elif action == storage.ACTION_BACKWARD:
                cmd.undo(obj)
            else:
                raise ValueError("Unsupported action %s" % action)

            self.storage.redo()
