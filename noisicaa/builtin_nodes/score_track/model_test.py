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

from typing import List

from noisidev import unittest
from noisidev import unittest_mixins
from noisidev import demo_project
from noisicaa import audioproc
from noisicaa import value_types
from noisicaa.music import base_track_test
from noisicaa.music import project
from . import model
from . import commands


class ScoreTrackConnectorTest(unittest_mixins.NodeDBMixin, unittest.AsyncTestCase):
    async def setup_testcase(self):
        self.pool = project.Pool()

    def test_foo(self):
        pr = demo_project.basic(self.pool, project.BaseProject, node_db=self.node_db)
        tr = pr.nodes[-1]

        messages = []  # type: List[str]

        connector = tr.create_node_connector(
            message_cb=messages.append, audioproc_client=None)
        try:
            messages.extend(connector.init())

            tr.insert_measure(1)
            m = tr.measure_list[1].measure
            m.notes.append(self.pool.create(model.Note, pitches=[value_types.Pitch('D#4')]))

            self.assertTrue(len(messages) > 0)

        finally:
            connector.close()


class ScoreTrackTest(base_track_test.TrackTestMixin, unittest.AsyncTestCase):
    node_uri = 'builtin://score-track'
    track_cls = model.ScoreTrack

    async def _fill_measure(self, measure):
        await self.client.send_command(commands.create_note(
            measure,
            idx=0,
            pitch=value_types.Pitch('F2'),
            duration=audioproc.MusicalDuration(1, 4)))
        self.assertEqual(len(measure.notes), 1)

    async def test_create_measure(self):
        track = await self._add_track()
        self.assertEqual(len(track.measure_list), 1)

        with self.project.apply_mutations():
            track.insert_measure(0)
        self.assertEqual(len(track.measure_list), 2)

    async def test_delete_measure(self):
        track = await self._add_track()
        self.assertEqual(len(track.measure_list), 1)

        with self.project.apply_mutations():
            track.remove_measure(0)
        self.assertEqual(len(track.measure_list), 0)

    async def test_clear_measures(self):
        track = await self._add_track()
        self.assertEqual(len(track.measure_list), 1)
        old_measure = track.measure_list[0].measure

        with self.project.apply_mutations():
            track.measure_list[0].clear_measure()
        self.assertIsNot(old_measure, track.measure_list[0].measure)

    async def test_create_note(self):
        track = await self._add_track()
        measure = track.measure_list[0].measure
        self.assertEqual(len(measure.notes), 0)

        await self.client.send_command(commands.create_note(
            measure,
            idx=0,
            pitch=value_types.Pitch('F2'),
            duration=audioproc.MusicalDuration(1, 4)))
        self.assertEqual(len(measure.notes), 1)
        self.assertEqual(measure.notes[0].pitches[0], value_types.Pitch('F2'))
        self.assertEqual(measure.notes[0].base_duration, audioproc.MusicalDuration(1, 4))

    async def test_delete_note(self):
        track = await self._add_track()
        measure = track.measure_list[0].measure
        await self._fill_measure(measure)

        await self.client.send_command(commands.delete_note(
            measure.notes[0]))
        self.assertEqual(len(measure.notes), 0)

    async def test_note_set_pitch(self):
        track = await self._add_track()
        measure = track.measure_list[0].measure
        await self._fill_measure(measure)

        await self.client.send_command(commands.update_note(
            measure.notes[0],
            set_pitch=value_types.Pitch('C2')))
        self.assertEqual(measure.notes[0].pitches[0], value_types.Pitch('C2'))

    async def test_note_add_pitch(self):
        track = await self._add_track()
        measure = track.measure_list[0].measure
        await self._fill_measure(measure)

        await self.client.send_command(commands.update_note(
            measure.notes[0],
            add_pitch=value_types.Pitch('C2')))
        self.assertEqual(len(measure.notes[0].pitches), 2)
        self.assertEqual(measure.notes[0].pitches[1], value_types.Pitch('C2'))

    async def test_note_remove_pitch(self):
        track = await self._add_track()
        measure = track.measure_list[0].measure
        await self._fill_measure(measure)
        await self.client.send_command(commands.update_note(
            measure.notes[0],
            add_pitch=value_types.Pitch('C2')))
        self.assertEqual(len(measure.notes[0].pitches), 2)

        await self.client.send_command(commands.update_note(
            measure.notes[0],
            remove_pitch=0))
        self.assertEqual(len(measure.notes[0].pitches), 1)
        self.assertEqual(measure.notes[0].pitches[0], value_types.Pitch('C2'))

    async def test_note_set_duration(self):
        track = await self._add_track()
        measure = track.measure_list[0].measure
        await self._fill_measure(measure)

        await self.client.send_command(commands.update_note(
            measure.notes[0],
            set_duration=audioproc.MusicalDuration(1, 2)))
        self.assertEqual(measure.notes[0].base_duration, audioproc.MusicalDuration(1, 2))

    async def test_note_set_dots(self):
        track = await self._add_track()
        measure = track.measure_list[0].measure
        await self._fill_measure(measure)

        await self.client.send_command(commands.update_note(
            measure.notes[0],
            set_dots=1))
        self.assertEqual(measure.notes[0].dots, 1)

    async def test_note_set_tuplet(self):
        track = await self._add_track()
        measure = track.measure_list[0].measure
        await self._fill_measure(measure)

        await self.client.send_command(commands.update_note(
            measure.notes[0],
            set_tuplet=3))
        self.assertEqual(measure.notes[0].tuplet, 3)

    async def test_note_set_accidental(self):
        track = await self._add_track()
        measure = track.measure_list[0].measure
        await self._fill_measure(measure)

        await self.client.send_command(commands.update_note(
            measure.notes[0],
            set_accidental=(0, '#')))
        self.assertEqual(measure.notes[0].pitches[0], value_types.Pitch('F#2'))

    async def test_note_transpose(self):
        track = await self._add_track()
        measure = track.measure_list[0].measure
        await self._fill_measure(measure)

        await self.client.send_command(commands.update_note(
            measure.notes[0],
            transpose=2))
        self.assertEqual(measure.notes[0].pitches[0], value_types.Pitch('G2'))

    async def test_paste_overwrite(self):
        track = await self._add_track()
        measure = track.measure_list[0].measure
        await self._fill_measure(measure)

        clipboard = measure.serialize()

        with self.project.apply_mutations():
            self.project.paste_measures(
                mode='overwrite',
                src_objs=[clipboard],
                targets=[track.measure_list[0]])
        new_measure = track.measure_list[0].measure
        self.assertNotEqual(new_measure.id, measure.id)
        self.assertEqual(new_measure.notes[0].pitches[0], value_types.Pitch('F2'))

    async def test_paste_link(self):
        track = await self._add_track()
        while len(track.measure_list) < 3:
            with self.project.apply_mutations():
                track.insert_measure(-1)

        measure = track.measure_list[0].measure
        await self._fill_measure(measure)

        clipboard = measure.serialize()

        with self.project.apply_mutations():
            self.project.paste_measures(
                mode='link',
                src_objs=[clipboard],
                targets=[track.measure_list[1], track.measure_list[2]])
        self.assertIs(track.measure_list[1].measure, measure)
        self.assertIs(track.measure_list[2].measure, measure)
