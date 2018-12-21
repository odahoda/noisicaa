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

from typing import Type  # pylint: disable=unused-import

from noisidev import unittest
from noisicaa import audioproc
from noisicaa import model
from . import pmodel


class ModelTest(unittest.TestCase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.pool = None  # type: model.Pool

    def setup_testcase(self):
        self.pool = pmodel.Pool()
        self.pool.register_class(pmodel.Project)
        self.pool.register_class(pmodel.MeasureReference)
        self.pool.register_class(pmodel.ScoreMeasure)
        self.pool.register_class(pmodel.ScoreTrack)
        self.pool.register_class(pmodel.Beat)
        self.pool.register_class(pmodel.BeatMeasure)
        self.pool.register_class(pmodel.BeatTrack)
        self.pool.register_class(pmodel.SampleRef)
        self.pool.register_class(pmodel.SampleTrack)
        self.pool.register_class(pmodel.ControlPoint)
        self.pool.register_class(pmodel.ControlTrack)
        self.pool.register_class(pmodel.Metadata)
        self.pool.register_class(pmodel.Sample)
        self.pool.register_class(pmodel.Note)
        self.pool.register_class(pmodel.PipelineGraphConnection)
        self.pool.register_class(pmodel.PipelineGraphNode)
        self.pool.register_class(pmodel.InstrumentPipelineGraphNode)
        self.pool.register_class(pmodel.AudioOutPipelineGraphNode)
        self.pool.register_class(pmodel.PipelineGraphControlValue)


class ProjectTest(ModelTest):
    def test_bpm(self):
        pr = self.pool.create(pmodel.Project)
        self.assertEqual(pr.bpm, 120)
        pr.bpm = 140
        self.assertEqual(pr.bpm, 140)

    def test_metadata(self):
        pr = self.pool.create(pmodel.Project)
        with self.assertRaises(ValueError):
            pr.metadata  # pylint: disable=pointless-statement
        pr.metadata = self.pool.create(pmodel.Metadata)
        self.assertIsInstance(pr.metadata, pmodel.Metadata)

    def test_samples(self):
        pr = self.pool.create(pmodel.Project)
        self.assertEqual(len(pr.samples), 0)
        pr.samples.append(self.pool.create(pmodel.Sample))

    def test_pipeline_graph_nodes(self):
        pr = self.pool.create(pmodel.Project)
        self.assertEqual(len(pr.pipeline_graph_nodes), 0)
        pr.pipeline_graph_nodes.append(self.pool.create(pmodel.PipelineGraphNode))

    def test_pipeline_graph_connections(self):
        pr = self.pool.create(pmodel.Project)
        self.assertEqual(len(pr.pipeline_graph_connections), 0)
        pr.pipeline_graph_connections.append(self.pool.create(pmodel.PipelineGraphConnection))


class MetadataTest(ModelTest):
    def test_author(self):
        md = self.pool.create(pmodel.Metadata)
        self.assertIsNone(md.author)
        md.author = "pink"
        self.assertEqual(md.author, "pink")

    def test_license(self):
        md = self.pool.create(pmodel.Metadata)
        self.assertIsNone(md.license)
        md.license = "CC0"
        self.assertEqual(md.license, "CC0")

    def test_copyright(self):
        md = self.pool.create(pmodel.Metadata)
        self.assertIsNone(md.copyright)
        md.copyright = "odahoda"
        self.assertEqual(md.copyright, "odahoda")

    def test_created(self):
        md = self.pool.create(pmodel.Metadata)
        self.assertIsNone(md.created)
        md.created = 2018
        self.assertEqual(md.created, 2018)


class PipelineGraphConnectionTest(ModelTest):
    def test_source_node(self):
        conn = self.pool.create(pmodel.PipelineGraphConnection)

        n1 = self.pool.create(pmodel.PipelineGraphNode)
        conn.source_node = n1
        self.assertIs(conn.source_node, n1)

    def test_source_port(self):
        conn = self.pool.create(pmodel.PipelineGraphConnection)

        conn.source_port = 'p1'
        self.assertEqual(conn.source_port, 'p1')

    def test_dest_node(self):
        conn = self.pool.create(pmodel.PipelineGraphConnection)

        n2 = self.pool.create(pmodel.PipelineGraphNode)
        conn.dest_node = n2
        self.assertIs(conn.dest_node, n2)

    def test_dest_port(self):
        conn = self.pool.create(pmodel.PipelineGraphConnection)

        conn.dest_port = 'p2'
        self.assertEqual(conn.dest_port, 'p2')


class BasePipelineGraphNodeMixin(object):
    cls = None  # type: Type[pmodel.BasePipelineGraphNode]

    def test_name(self):
        node = self.pool.create(self.cls)

        node.name = 'n1'
        self.assertEqual(node.name, 'n1')

    def test_graph_pos(self):
        node = self.pool.create(self.cls)

        node.graph_pos = model.Pos2F(12, 14)
        self.assertEqual(node.graph_pos, model.Pos2F(12, 14))

    def test_graph_size(self):
        node = self.pool.create(self.cls)

        node.graph_size = model.SizeF(20, 32)
        self.assertEqual(node.graph_size, model.SizeF(20, 32))

    def test_graph_color(self):
        node = self.pool.create(self.cls)

        node.graph_color = model.Color(0.5, 0.4, 0.3, 0.1)
        self.assertEqual(node.graph_color, model.Color(0.5, 0.4, 0.3, 0.1))

    def test_plugin_state(self):
        node = self.pool.create(self.cls)

        plugin_state = audioproc.PluginState(
            lv2=audioproc.PluginStateLV2(
                properties=[
                    audioproc.PluginStateLV2Property(
                        key='knob1',
                        type='uri://int',
                        value=b'123')]))

        node.plugin_state = plugin_state
        self.assertEqual(node.plugin_state, plugin_state)

    def test_control_values(self):
        node = self.pool.create(self.cls)

        cv1 = self.pool.create(pmodel.PipelineGraphControlValue)
        node.control_values.append(cv1)
        self.assertIs(node.control_values[0], cv1)


class InstrumentPipelineGraphNodeTest(BasePipelineGraphNodeMixin, ModelTest):
    cls = pmodel.InstrumentPipelineGraphNode

    def test_instrument_pipeline_graph_node(self):
        node = self.pool.create(self.cls)

        node.instrument_uri = 'sf2:/path.sf2?bank=1&preset=3'
        self.assertEqual(node.instrument_uri, 'sf2:/path.sf2?bank=1&preset=3')


class PipelineGraphNodeTest(BasePipelineGraphNodeMixin, ModelTest):
    cls = pmodel.PipelineGraphNode

    def test_pipeline_graph_node(self):
        node = self.pool.create(self.cls)

        node.node_uri = 'uri://some/name'
        self.assertEqual(node.node_uri, 'uri://some/name')


class PipelineGraphControlValueTest(ModelTest):
    def test_name(self):
        cv = self.pool.create(pmodel.PipelineGraphControlValue)

        cv.name = 'gain'
        self.assertEqual(cv.name, 'gain')

    def test_value(self):
        cv = self.pool.create(pmodel.PipelineGraphControlValue)

        cv.value = model.ControlValue(value=12, generation=1)
        self.assertEqual(
            cv.value,
            model.ControlValue(value=12, generation=1))


class TrackMixin(BasePipelineGraphNodeMixin):
    cls = None  # type: Type[pmodel.Track]


class MeasuredTrackMixin(TrackMixin):
    cls = None  # type: Type[pmodel.MeasuredTrack]
    measure_cls = None  # type: Type[pmodel.Measure]

    def test_measure_list(self):
        track = self.pool.create(self.cls)

        ref = self.pool.create(pmodel.MeasureReference)
        track.measure_list.append(ref)
        self.assertIs(track.measure_list[0], ref)

    def test_measure_heap(self):
        track = self.pool.create(self.cls)

        measure = self.pool.create(self.measure_cls)
        track.measure_heap.append(measure)
        self.assertIs(track.measure_heap[0], measure)


class SampleTrackTest(TrackMixin, ModelTest):
    cls = pmodel.SampleTrack

    def test_samples(self):
        track = self.pool.create(self.cls)

        smpl = self.pool.create(pmodel.SampleRef)
        track.samples.append(smpl)
        self.assertIs(track.samples[0], smpl)


class SampleRefTest(ModelTest):
    def test_time(self):
        ref = self.pool.create(pmodel.SampleRef)

        ref.time = audioproc.MusicalTime(1, 4)
        self.assertEqual(ref.time, audioproc.MusicalTime(1, 4))

    def test_sample(self):
        ref = self.pool.create(pmodel.SampleRef)

        smpl = self.pool.create(pmodel.Sample)
        ref.sample = smpl
        self.assertIs(ref.sample, smpl)


class ScoreTrackTest(MeasuredTrackMixin, ModelTest):
    cls = pmodel.ScoreTrack
    measure_cls = pmodel.ScoreMeasure

    def test_transpose_octaves(self):
        track = self.pool.create(self.cls)

        self.assertEqual(track.transpose_octaves, 0)
        track.transpose_octaves = -2
        self.assertEqual(track.transpose_octaves, -2)


class ScoreMeasureTest(ModelTest):
    def test_clef(self):
        measure = self.pool.create(pmodel.ScoreMeasure)

        self.assertEqual(measure.clef, model.Clef.Treble)
        measure.clef = model.Clef.Tenor
        self.assertEqual(measure.clef, model.Clef.Tenor)

    def test_key_signature(self):
        measure = self.pool.create(pmodel.ScoreMeasure)

        self.assertEqual(measure.key_signature, model.KeySignature('C major'))
        measure.key_signature = model.KeySignature('F minor')
        self.assertEqual(measure.key_signature, model.KeySignature('F minor'))

    def test_time_signature(self):
        measure = self.pool.create(pmodel.ScoreMeasure)

        self.assertEqual(measure.time_signature, model.TimeSignature(4, 4))
        measure.time_signature = model.TimeSignature(3, 4)
        self.assertEqual(measure.time_signature, model.TimeSignature(3, 4))

    def test_notes(self):
        measure = self.pool.create(pmodel.ScoreMeasure)

        note = self.pool.create(pmodel.Note)
        measure.notes.append(note)
        self.assertIs(measure.notes[0], note)


class BeatTrackTest(MeasuredTrackMixin, ModelTest):
    cls = pmodel.BeatTrack
    measure_cls = pmodel.BeatMeasure

    def test_pitch(self):
        track = self.pool.create(self.cls)

        track.pitch = model.Pitch('F4')
        self.assertEqual(track.pitch, model.Pitch('F4'))


class BeatMeasureTest(ModelTest):
    def test_beats(self):
        measure = self.pool.create(pmodel.BeatMeasure)

        beat = self.pool.create(pmodel.Beat)
        measure.beats.append(beat)
        self.assertIs(measure.beats[0], beat)


class BeatTest(ModelTest):
    def test_time(self):
        beat = self.pool.create(pmodel.Beat)

        beat.time = audioproc.MusicalDuration(1, 4)
        self.assertEqual(beat.time, audioproc.MusicalDuration(1, 4))

    def test_velocity(self):
        beat = self.pool.create(pmodel.Beat)

        beat.velocity = 120
        self.assertEqual(beat.velocity, 120)



class ControlTrackTest(TrackMixin, ModelTest):
    cls = pmodel.ControlTrack

    def test_points(self):
        track = self.pool.create(self.cls)

        pnt = self.pool.create(pmodel.ControlPoint)
        track.points.append(pnt)
        self.assertIs(track.points[0], pnt)


class MeasureReferenceTest(ModelTest):
    def test_measure(self):
        ref = self.pool.create(pmodel.MeasureReference)

        measure = self.pool.create(pmodel.ScoreMeasure)
        ref.measure = measure
        self.assertIs(ref.measure, measure)


class NoteTest(ModelTest):
    def test_pitches(self):
        note = self.pool.create(pmodel.Note)
        self.assertEqual(len(note.pitches), 0)

        note.pitches.append(model.Pitch('C4'))
        note.pitches.append(model.Pitch('D4'))
        note.pitches.append(model.Pitch('E4'))
        note.pitches.append(model.Pitch('F4'))
        del note.pitches[2]
        note.pitches.insert(1, model.Pitch('G4'))
        self.assertEqual(
            note.pitches,
            [model.Pitch('C4'), model.Pitch('G4'), model.Pitch('D4'), model.Pitch('F4')])

    def test_base_duration(self):
        note = self.pool.create(pmodel.Note)

        note.base_duration = audioproc.MusicalDuration(1, 2)
        self.assertEqual(note.base_duration, audioproc.MusicalDuration(1, 2))

    def test_dots(self):
        note = self.pool.create(pmodel.Note)

        self.assertEqual(note.dots, 0)
        note.dots = 2
        self.assertEqual(note.dots, 2)

    def test_tuplet(self):
        note = self.pool.create(pmodel.Note)

        self.assertEqual(note.tuplet, 0)
        note.tuplet = 3
        self.assertEqual(note.tuplet, 3)


class SampleTest(ModelTest):
    def test_path(self):
        smpl = self.pool.create(pmodel.Sample)

        smpl.path = '/foo'
        self.assertEqual(smpl.path, '/foo')
