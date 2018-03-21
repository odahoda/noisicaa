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

import os.path
import textwrap

from . import unittest
from noisicaa.audioproc import (
    MusicalTime,
    MusicalDuration,
)
from noisicaa.music import (
    Pitch,
    Note,
    score_track,
    sample_track,
    beat_track,
    control_track,
    pipeline_graph,
)

def basic(cls, **kwargs):
    project = cls(**kwargs)
    project.bpm = 140

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
        Note(pitches=[Pitch('C5')], base_duration=MusicalDuration(1, 4)))
    track1.measure_list[0].measure.notes.append(
        Note(pitches=[Pitch('D5')], base_duration=MusicalDuration(1, 4)))
    track1.measure_list[0].measure.notes.append(
        Note(pitches=[Pitch('E5')], base_duration=MusicalDuration(1, 4)))
    track1.measure_list[0].measure.notes.append(
        Note(pitches=[Pitch('F5')], base_duration=MusicalDuration(1, 4)))

    track1.measure_list[1].measure.notes.append(
        Note(pitches=[Pitch('C5')], base_duration=MusicalDuration(1, 2)))
    track1.measure_list[1].measure.notes.append(
        Note(pitches=[Pitch('F5')], base_duration=MusicalDuration(1, 8)))
    track1.measure_list[1].measure.notes.append(
        Note(pitches=[Pitch('E5')], base_duration=MusicalDuration(1, 8)))
    track1.measure_list[1].measure.notes.append(
        Note(pitches=[Pitch('D5')], base_duration=MusicalDuration(1, 4)))

    track1.measure_list[2].measure.notes.append(
        Note(pitches=[Pitch('C5')], base_duration=MusicalDuration(1, 4)))
    track1.measure_list[2].measure.notes.append(
        Note(pitches=[Pitch('D5')], base_duration=MusicalDuration(1, 4)))
    track1.measure_list[2].measure.notes.append(
        Note(pitches=[Pitch('E5')], base_duration=MusicalDuration(1, 4)))
    track1.measure_list[2].measure.notes.append(
        Note(pitches=[Pitch('F5')], base_duration=MusicalDuration(1, 4)))

    track1.measure_list[3].measure.notes.append(
        Note(pitches=[Pitch('C5')], base_duration=MusicalDuration(1, 2)))
    track1.measure_list[3].measure.notes.append(
        Note(pitches=[Pitch('F5')], base_duration=MusicalDuration(1, 8)))
    track1.measure_list[3].measure.notes.append(
        Note(pitches=[Pitch('E5')], base_duration=MusicalDuration(1, 8)))
    track1.measure_list[3].measure.notes.append(
        Note(pitches=[Pitch('D5')], base_duration=MusicalDuration(1, 4)))

    track1.measure_list[4].measure.notes.append(
        Note(pitches=[Pitch('C5')], base_duration=MusicalDuration(1, 1)))


    track2.measure_list[0].measure.notes.append(
        Note(pitches=[Pitch('C4'), Pitch('E3'), Pitch('G3')],
             base_duration=MusicalDuration(1, 1)))
    track2.measure_list[1].measure.notes.append(
        Note(pitches=[Pitch('F3'), Pitch('A4'), Pitch('C4')],
             base_duration=MusicalDuration(1, 1)))

    track2.measure_list[2].measure.notes.append(
        Note(pitches=[Pitch('A3'), Pitch('C4'), Pitch('E4')],
             base_duration=MusicalDuration(1, 1)))
    track2.measure_list[3].measure.notes.append(
        Note(pitches=[Pitch('C4'), Pitch('E3'), Pitch('G3')],
             base_duration=MusicalDuration(1, 1)))

    track2.measure_list[4].measure.notes.append(
        Note(pitches=[Pitch('C4'), Pitch('E3'), Pitch('G3')],
             base_duration=MusicalDuration(1, 1)))

    return project


def complex(cls, **kwargs):  # pylint: disable=redefined-builtin
    project = cls(**kwargs)
    project.bpm = 140

    master_mixer = project.master_group.mixer_node

    while len(project.property_track.measure_list) < 4:
        project.property_track.append_measure()

    track1 = score_track.ScoreTrack(
        name="Track 1",
        instrument='sf2:/usr/share/sounds/sf2/FluidR3_GM.sf2?bank=0&preset=0',  # Piano
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

    # TODO: custom_csound currently not supported
    # filter_node_uri = 'builtin://custom_csound'
    # filter_node = pipeline_graph.PipelineGraphNode(
    #     name='Filter',
    #     node_uri=filter_node_uri)
    # filter_node.set_parameter(
    #     'csound_orchestra',
    #     textwrap.dedent('''\
    #         instr 2
    #             printk(0.5, k(gaCtrl))
    #             gaOutLeft = butterlp(gaInLeft, 200 + 2000 * gaCtrl)
    #             gaOutRight = butterlp(gaInRight, 200 + 2000 * gaCtrl)
    #         endin
    #     '''))
    # project.add_pipeline_graph_node(filter_node)

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
            dest_node=master_mixer, dest_port='in:left'))
    project.add_pipeline_graph_connection(
        pipeline_graph.PipelineGraphConnection(
            source_node=eq_node, source_port='Output R',
            dest_node=master_mixer, dest_port='in:right'))

    for i in range(4):
        track1.measure_list[i].measure.notes.append(
            Note(pitches=[Pitch('C4')], base_duration=MusicalDuration(1, 4)))
        track1.measure_list[i].measure.notes.append(
            Note(pitches=[Pitch('E4')], base_duration=MusicalDuration(1, 4)))
        track1.measure_list[i].measure.notes.append(
            Note(pitches=[Pitch('G4')], base_duration=MusicalDuration(1, 2)))

    track2 = beat_track.BeatTrack(
        name="Track 2",
        instrument='sf2:/usr/share/sounds/sf2/FluidR3_GM.sf2?bank=0&preset=118',  # Synth Drum
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
            beat_track.Beat(time=MusicalDuration(0, 4), velocity=100))
        track2.measure_list[i].measure.beats.append(
            beat_track.Beat(time=MusicalDuration(1, 4), velocity=80))
        track2.measure_list[i].measure.beats.append(
            beat_track.Beat(time=MusicalDuration(2, 4), velocity=60))
        track2.measure_list[i].measure.beats.append(
            beat_track.Beat(time=MusicalDuration(3, 4), velocity=40))

    track3 = sample_track.SampleTrack(
        name="Track 3")
    project.add_track(project.master_group, 2, track3)

    smpl = sample_track.Sample(
        path=os.path.join(unittest.TESTDATA_DIR, 'future-thunder1.wav'))
    project.samples.append(smpl)

    track3.samples.append(
        sample_track.SampleRef(time=MusicalTime(2, 4), sample_id=smpl.id))
    track3.samples.append(
        sample_track.SampleRef(time=MusicalTime(14, 4), sample_id=smpl.id))

    track4 = control_track.ControlTrack(
        name="Track 4")
    project.add_track(project.master_group, 3, track4)

    track4.points.append(
        control_track.ControlPoint(time=MusicalTime(0, 4), value=1.0))
    track4.points.append(
        control_track.ControlPoint(time=MusicalTime(4, 4), value=0.0))
    track4.points.append(
        control_track.ControlPoint(time=MusicalTime(8, 4), value=1.0))

    # project.add_pipeline_graph_connection(
    #     pipeline_graph.PipelineGraphConnection(
    #         source_node=track4.generator_node, source_port='out',
    #         dest_node=filter_node, dest_port='ctrl'))

    return project
