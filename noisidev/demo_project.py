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
from noisicaa.model import (
    Pitch,
)
from noisicaa.music import (
    score_track,
    sample_track,
    beat_track,
    control_track,
    pipeline_graph,
)
from noisicaa import instrument_db

Note = score_track.Note


def empty(pool, cls, **kwargs):
    project = pool.create(cls, **kwargs)
    project.bpm = 140

    return project


def basic(pool, cls, **kwargs):
    project = pool.create(cls, **kwargs)
    project.bpm = 140

    audio_out = project.audio_out_node

    track1_instr = pool.create(
        pipeline_graph.InstrumentPipelineGraphNode,
        name="Track 1 - Instrument",
        instrument_uri='sf2:/usr/share/sounds/sf2/FluidR3_GM.sf2?bank=0&preset=0')
    project.add_pipeline_graph_node(track1_instr)

    project.add_pipeline_graph_connection(pool.create(
        pipeline_graph.PipelineGraphConnection,
        source_node=track1_instr, source_port='out:left',
        dest_node=audio_out, dest_port='in:left'))

    project.add_pipeline_graph_connection(pool.create(
        pipeline_graph.PipelineGraphConnection,
        source_node=track1_instr, source_port='out:right',
        dest_node=audio_out, dest_port='in:right'))

    track1 = pool.create(
        score_track.ScoreTrack,
        name="Track 1 - Events",
        num_measures=5)
    project.add_pipeline_graph_node(track1)

    project.add_pipeline_graph_connection(pool.create(
        pipeline_graph.PipelineGraphConnection,
        source_node=track1, source_port='out',
        dest_node=track1_instr, dest_port='in'))

    track1.measure_list[0].measure.notes.append(
        pool.create(Note, pitches=[Pitch('C5')], base_duration=MusicalDuration(1, 4)))
    track1.measure_list[0].measure.notes.append(
        pool.create(Note, pitches=[Pitch('D5')], base_duration=MusicalDuration(1, 4)))
    track1.measure_list[0].measure.notes.append(
        pool.create(Note, pitches=[Pitch('E5')], base_duration=MusicalDuration(1, 4)))
    track1.measure_list[0].measure.notes.append(
        pool.create(Note, pitches=[Pitch('F5')], base_duration=MusicalDuration(1, 4)))

    track1.measure_list[1].measure.notes.append(
        pool.create(Note, pitches=[Pitch('C5')], base_duration=MusicalDuration(1, 2)))
    track1.measure_list[1].measure.notes.append(
        pool.create(Note, pitches=[Pitch('F5')], base_duration=MusicalDuration(1, 8)))
    track1.measure_list[1].measure.notes.append(
        pool.create(Note, pitches=[Pitch('E5')], base_duration=MusicalDuration(1, 8)))
    track1.measure_list[1].measure.notes.append(
        pool.create(Note, pitches=[Pitch('D5')], base_duration=MusicalDuration(1, 4)))

    track1.measure_list[2].measure.notes.append(
        pool.create(Note, pitches=[Pitch('C5')], base_duration=MusicalDuration(1, 4)))
    track1.measure_list[2].measure.notes.append(
        pool.create(Note, pitches=[Pitch('D5')], base_duration=MusicalDuration(1, 4)))
    track1.measure_list[2].measure.notes.append(
        pool.create(Note, pitches=[Pitch('E5')], base_duration=MusicalDuration(1, 4)))
    track1.measure_list[2].measure.notes.append(
        pool.create(Note, pitches=[Pitch('F5')], base_duration=MusicalDuration(1, 4)))

    track1.measure_list[3].measure.notes.append(
        pool.create(Note, pitches=[Pitch('C5')], base_duration=MusicalDuration(1, 2)))
    track1.measure_list[3].measure.notes.append(
        pool.create(Note, pitches=[Pitch('F5')], base_duration=MusicalDuration(1, 8)))
    track1.measure_list[3].measure.notes.append(
        pool.create(Note, pitches=[Pitch('E5')], base_duration=MusicalDuration(1, 8)))
    track1.measure_list[3].measure.notes.append(
        pool.create(Note, pitches=[Pitch('D5')], base_duration=MusicalDuration(1, 4)))

    track1.measure_list[4].measure.notes.append(
        pool.create(Note, pitches=[Pitch('C5')], base_duration=MusicalDuration(1, 1)))


    track2_instr = pool.create(
        pipeline_graph.InstrumentPipelineGraphNode,
        name="Track 2 - Instrument",
        instrument_uri='sf2:/usr/share/sounds/sf2/FluidR3_GM.sf2?bank=0&preset=73')
    project.add_pipeline_graph_node(track2_instr)

    project.add_pipeline_graph_connection(pool.create(
        pipeline_graph.PipelineGraphConnection,
        source_node=track2_instr, source_port='out:left',
        dest_node=audio_out, dest_port='in:left'))

    project.add_pipeline_graph_connection(pool.create(
        pipeline_graph.PipelineGraphConnection,
        source_node=track2_instr, source_port='out:right',
        dest_node=audio_out, dest_port='in:right'))

    track2 = pool.create(
        score_track.ScoreTrack,
        name="Track 2 - Events",
        num_measures=5)
    project.add_pipeline_graph_node(track2)

    project.add_pipeline_graph_connection(pool.create(
        pipeline_graph.PipelineGraphConnection,
        source_node=track2, source_port='out',
        dest_node=track2_instr, dest_port='in'))

    track2.measure_list[0].measure.notes.append(pool.create(
        Note, pitches=[Pitch('C4'), Pitch('E3'), Pitch('G3')], base_duration=MusicalDuration(1, 1)))
    track2.measure_list[1].measure.notes.append(pool.create(
        Note, pitches=[Pitch('F3'), Pitch('A4'), Pitch('C4')], base_duration=MusicalDuration(1, 1)))

    track2.measure_list[2].measure.notes.append(pool.create(
        Note, pitches=[Pitch('A3'), Pitch('C4'), Pitch('E4')], base_duration=MusicalDuration(1, 1)))
    track2.measure_list[3].measure.notes.append(pool.create(
        Note, pitches=[Pitch('C4'), Pitch('E3'), Pitch('G3')], base_duration=MusicalDuration(1, 1)))

    track2.measure_list[4].measure.notes.append(pool.create(
        Note, pitches=[Pitch('C4'), Pitch('E3'), Pitch('G3')], base_duration=MusicalDuration(1, 1)))

    return project


def complex(pool, cls, **kwargs):  # pylint: disable=redefined-builtin
    project = pool.create(cls, **kwargs)
    project.bpm = 140

    audio_out = project.audio_out_node

    ## track 1
    # score_track -> instrument -> eq -> out

    eq_node_uri = 'ladspa://dj_eq_1901.so/dj_eq'
    eq_node = pool.create(pipeline_graph.PipelineGraphNode, name='EQ', node_uri=eq_node_uri)
    project.add_pipeline_graph_node(eq_node)
    eq_node.set_control_value('Lo gain (dB)', -40.0, 1)
    eq_node.set_control_value('Mid gain (dB)', 0.0, 1)
    eq_node.set_control_value('Hi gain (dB)', 5.0, 1)

    project.add_pipeline_graph_connection(pool.create(
        pipeline_graph.PipelineGraphConnection,
        source_node=eq_node, source_port='Output L',
        dest_node=audio_out, dest_port='in:left'))
    project.add_pipeline_graph_connection(pool.create(
        pipeline_graph.PipelineGraphConnection,
        source_node=eq_node, source_port='Output R',
        dest_node=audio_out, dest_port='in:right'))

    track1_instr = pool.create(
        pipeline_graph.InstrumentPipelineGraphNode,
        name="Track 1 - Instrument",
        instrument_uri='sf2:/usr/share/sounds/sf2/FluidR3_GM.sf2?bank=0&preset=0')
    project.add_pipeline_graph_node(track1_instr)

    project.add_pipeline_graph_connection(pool.create(
        pipeline_graph.PipelineGraphConnection,
        source_node=track1_instr, source_port='out:left',
        dest_node=eq_node, dest_port='Input L'))
    project.add_pipeline_graph_connection(pool.create(
        pipeline_graph.PipelineGraphConnection,
        source_node=track1_instr, source_port='out:right',
        dest_node=eq_node, dest_port='Input R'))

    track1 = pool.create(
        score_track.ScoreTrack,
        name="Track 1",
        num_measures=4)
    project.add_pipeline_graph_node(track1)

    project.add_pipeline_graph_connection(pool.create(
        pipeline_graph.PipelineGraphConnection,
        source_node=track1, source_port='out',
        dest_node=track1_instr, dest_port='in'))

    for i in range(4):
        track1.measure_list[i].measure.notes.append(
            pool.create(Note, pitches=[Pitch('C4')], base_duration=MusicalDuration(1, 4)))
        track1.measure_list[i].measure.notes.append(
            pool.create(Note, pitches=[Pitch('E4')], base_duration=MusicalDuration(1, 4)))
        track1.measure_list[i].measure.notes.append(
            pool.create(Note, pitches=[Pitch('G4')], base_duration=MusicalDuration(1, 2)))


    ## track 2
    # beat_track -> instrument -> delay -> reverb -> out

    reverb_node_uri = 'builtin://csound/reverb'
    reverb_node = pool.create(
        pipeline_graph.PipelineGraphNode, name='Reverb',node_uri=reverb_node_uri)
    project.add_pipeline_graph_node(reverb_node)

    project.add_pipeline_graph_connection(pool.create(
        pipeline_graph.PipelineGraphConnection,
        source_node=reverb_node, source_port='out:left',
        dest_node=audio_out, dest_port='in:left'))
    project.add_pipeline_graph_connection(pool.create(
        pipeline_graph.PipelineGraphConnection,
        source_node=reverb_node, source_port='out:right',
        dest_node=audio_out, dest_port='in:right'))

    delay_node_uri = 'http://drobilla.net/plugins/mda/Delay'
    delay_node = pool.create(
        pipeline_graph.PipelineGraphNode, name='Delay', node_uri=delay_node_uri)
    project.add_pipeline_graph_node(delay_node)
    delay_node.set_control_value('l_delay', 0.3, 1)
    delay_node.set_control_value('r_delay', 0.31, 1)

    project.add_pipeline_graph_connection(pool.create(
        pipeline_graph.PipelineGraphConnection,
        source_node=delay_node, source_port='left_out',
        dest_node=reverb_node, dest_port='in:left'))
    project.add_pipeline_graph_connection(pool.create(
        pipeline_graph.PipelineGraphConnection,
        source_node=delay_node, source_port='right_out',
        dest_node=reverb_node, dest_port='in:right'))

    track2_instr = pool.create(
        pipeline_graph.InstrumentPipelineGraphNode,
        name="Track 2 - Instrument",
        instrument_uri='sf2:/usr/share/sounds/sf2/FluidR3_GM.sf2?bank=0&preset=118')  # Synth Drum
    project.add_pipeline_graph_node(track2_instr)

    project.add_pipeline_graph_connection(pool.create(
        pipeline_graph.PipelineGraphConnection,
        source_node=track2_instr, source_port='out:left',
        dest_node=delay_node, dest_port='left_in'))
    project.add_pipeline_graph_connection(pool.create(
        pipeline_graph.PipelineGraphConnection,
        source_node=track2_instr, source_port='out:right',
        dest_node=delay_node, dest_port='right_in'))

    track2 = pool.create(
        beat_track.BeatTrack,
        name="Track 2",
        num_measures=4)
    track2.pitch = Pitch('C4')
    project.add_pipeline_graph_node(track2)

    project.add_pipeline_graph_connection(pool.create(
        pipeline_graph.PipelineGraphConnection,
        source_node=track1, source_port='out',
        dest_node=track1_instr, dest_port='in'))

    for i in range(4):
        track2.measure_list[i].measure.beats.append(
            pool.create(beat_track.Beat, time=MusicalDuration(0, 4), velocity=100))
        track2.measure_list[i].measure.beats.append(
            pool.create(beat_track.Beat, time=MusicalDuration(1, 4), velocity=80))
        track2.measure_list[i].measure.beats.append(
            pool.create(beat_track.Beat, time=MusicalDuration(2, 4), velocity=60))
        track2.measure_list[i].measure.beats.append(
            pool.create(beat_track.Beat, time=MusicalDuration(3, 4), velocity=40))


    ## track 3
    # sample_track -> out

    track3 = pool.create(sample_track.SampleTrack, name="Track 3")
    project.add_pipeline_graph_node(track3)

    project.add_pipeline_graph_connection(pool.create(
        pipeline_graph.PipelineGraphConnection,
        source_node=track3, source_port='out:left',
        dest_node=audio_out, dest_port='in:left'))
    project.add_pipeline_graph_connection(pool.create(
        pipeline_graph.PipelineGraphConnection,
        source_node=track3, source_port='out:right',
        dest_node=audio_out, dest_port='in:right'))

    smpl = pool.create(
        sample_track.Sample, path=os.path.join(unittest.TESTDATA_DIR, 'future-thunder1.wav'))
    project.samples.append(smpl)

    track3.samples.append(
        pool.create(sample_track.SampleRef, time=MusicalTime(2, 4), sample=smpl))
    track3.samples.append(
        pool.create(sample_track.SampleRef, time=MusicalTime(14, 4), sample=smpl))


    ## track 4
    # track4 = pool.create(control_track.ControlTrack, name="Track 4")
    # project.add_pipeline_graph_node(track4)

    # track4.points.append(
    #     pool.create(control_track.ControlPoint, time=MusicalTime(0, 4), value=1.0))
    # track4.points.append(
    #     pool.create(control_track.ControlPoint, time=MusicalTime(4, 4), value=0.0))
    # track4.points.append(
    #     pool.create(control_track.ControlPoint, time=MusicalTime(8, 4), value=1.0))

    # project.add_pipeline_graph_connection(
    #     pipeline_graph.PipelineGraphConnection(
    #         source_node=track4.generator_node, source_port='out',
    #         dest_node=filter_node, dest_port='ctrl'))

    return project
