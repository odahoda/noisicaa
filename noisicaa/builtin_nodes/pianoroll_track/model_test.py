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

import logging

from noisidev import unittest
from noisicaa import audioproc
from noisicaa import value_types
from noisicaa.music import base_track_test
from noisicaa.builtin_nodes import processor_message_registry_pb2
from . import model

MT = audioproc.MusicalTime
MD = audioproc.MusicalDuration
MEVT = value_types.MidiEvent
NOTE_ON = lambda channel, pitch, velocity: bytes([0x90 | channel, pitch, velocity])
NOTE_OFF = lambda channel, pitch: bytes([0x80 | channel, pitch, 0])


class PianoRollTrackTest(base_track_test.TrackTestMixin, unittest.AsyncTestCase):
    node_uri = 'builtin://pianoroll-track'
    track_cls = model.PianoRollTrack

    async def test_create_segment(self):
        track = await self._add_track()
        self.assertEqual(len(track.segments), 0)
        self.assertEqual(len(track.segment_heap), 0)

        with self.project.apply_mutations('test'):
            segment_ref = track.create_segment(MT(3, 4), MD(4, 4))
        self.assertEqual(segment_ref.time, MT(3, 4))
        self.assertEqual(segment_ref.segment.duration, MD(4, 4))
        self.assertEqual(len(track.segments), 1)
        self.assertIs(track.segments[0], segment_ref)
        self.assertEqual(len(track.segment_heap), 1)
        self.assertIs(track.segment_heap[0], segment_ref.segment)

    async def test_remove_segment(self):
        track = await self._add_track()
        with self.project.apply_mutations('test'):
            segment_ref = track.create_segment(MT(3, 4), MD(4, 4))

        with self.project.apply_mutations('test'):
            track.remove_segment(segment_ref)
        self.assertEqual(len(track.segments), 0)
        self.assertEqual(len(track.segment_heap), 0)

    async def test_split_segment(self):
        track = await self._add_track()
        with self.project.apply_mutations('test'):
            segment_ref = track.create_segment(MT(0, 4), MD(4, 4))
            segment = segment_ref.segment
            segment.add_event(MEVT(MT(0, 4), NOTE_ON(0, 70, 100)))
            segment.add_event(MEVT(MT(4, 4), NOTE_OFF(0, 70)))
            segment.add_event(MEVT(MT(0, 4), NOTE_ON(0, 60, 100)))
            segment.add_event(MEVT(MT(1, 4), NOTE_OFF(0, 60)))
            segment.add_event(MEVT(MT(1, 4), NOTE_ON(0, 61, 100)))
            segment.add_event(MEVT(MT(2, 4), NOTE_OFF(0, 61)))
            segment.add_event(MEVT(MT(2, 4), NOTE_ON(0, 62, 100)))
            segment.add_event(MEVT(MT(3, 4), NOTE_OFF(0, 62)))
            segment.add_event(MEVT(MT(3, 4), NOTE_ON(0, 63, 100)))
            segment.add_event(MEVT(MT(4, 4), NOTE_OFF(0, 63)))

        with self.project.apply_mutations('test'):
            track.split_segment(segment_ref, MT(2, 4))
        self.assertEqual(len(track.segments), 2)
        self.assertEqual(len(track.segment_heap), 2)
        self.assertEqual(
            {e.midi_event for e in track.segments[0].segment.events},
            {MEVT(MT(0, 4), NOTE_ON(0, 70, 100)),
             MEVT(MT(2, 4), NOTE_OFF(0, 70)),
             MEVT(MT(0, 4), NOTE_ON(0, 60, 100)),
             MEVT(MT(1, 4), NOTE_OFF(0, 60)),
             MEVT(MT(1, 4), NOTE_ON(0, 61, 100)),
             MEVT(MT(2, 4), NOTE_OFF(0, 61)),
            })
        self.assertEqual(
            {e.midi_event for e in track.segments[1].segment.events},
            {MEVT(MT(0, 4), NOTE_ON(0, 70, 100)),
             MEVT(MT(2, 4), NOTE_OFF(0, 70)),
             MEVT(MT(0, 4), NOTE_ON(0, 62, 100)),
             MEVT(MT(1, 4), NOTE_OFF(0, 62)),
             MEVT(MT(1, 4), NOTE_ON(0, 63, 100)),
             MEVT(MT(2, 4), NOTE_OFF(0, 63)),
            })

    async def test_copy_segment(self):
        track = await self._add_track()
        with self.project.apply_mutations('test'):
            segment_ref = track.create_segment(MT(0, 4), MD(4, 4))
            segment = segment_ref.segment
            segment.add_event(MEVT(MT(0, 4), NOTE_ON(0, 70, 100)))
            segment.add_event(MEVT(MT(4, 4), NOTE_OFF(0, 70)))
            segment.add_event(MEVT(MT(0, 4), NOTE_ON(0, 60, 100)))
            segment.add_event(MEVT(MT(1, 4), NOTE_OFF(0, 60)))
            segment.add_event(MEVT(MT(1, 4), NOTE_ON(0, 61, 100)))
            segment.add_event(MEVT(MT(2, 4), NOTE_OFF(0, 61)))
            segment.add_event(MEVT(MT(2, 4), NOTE_ON(0, 62, 100)))
            segment.add_event(MEVT(MT(3, 4), NOTE_OFF(0, 62)))
            segment.add_event(MEVT(MT(3, 4), NOTE_ON(0, 63, 100)))
            segment.add_event(MEVT(MT(4, 4), NOTE_OFF(0, 63)))

        data = track.copy_segments([segment_ref])
        self.assertEqual(len(data.segments), 1)

    async def test_cut_segment(self):
        track = await self._add_track()
        with self.project.apply_mutations('test'):
            segment_ref = track.create_segment(MT(0, 4), MD(4, 4))
            segment = segment_ref.segment
            segment.add_event(MEVT(MT(0, 4), NOTE_ON(0, 70, 100)))
            segment.add_event(MEVT(MT(4, 4), NOTE_OFF(0, 70)))
            segment.add_event(MEVT(MT(0, 4), NOTE_ON(0, 60, 100)))
            segment.add_event(MEVT(MT(1, 4), NOTE_OFF(0, 60)))
            segment.add_event(MEVT(MT(1, 4), NOTE_ON(0, 61, 100)))
            segment.add_event(MEVT(MT(2, 4), NOTE_OFF(0, 61)))
            segment.add_event(MEVT(MT(2, 4), NOTE_ON(0, 62, 100)))
            segment.add_event(MEVT(MT(3, 4), NOTE_OFF(0, 62)))
            segment.add_event(MEVT(MT(3, 4), NOTE_ON(0, 63, 100)))
            segment.add_event(MEVT(MT(4, 4), NOTE_OFF(0, 63)))

        with self.project.apply_mutations('test'):
            data = track.cut_segments([segment_ref])
        self.assertEqual(len(data.segments), 1)
        self.assertEqual(len(track.segments), 0)

    async def test_paste_segment(self):
        track = await self._add_track()
        with self.project.apply_mutations('test'):
            segment_ref = track.create_segment(MT(0, 4), MD(4, 4))
            segment = segment_ref.segment
            segment.add_event(MEVT(MT(0, 4), NOTE_ON(0, 70, 100)))
            segment.add_event(MEVT(MT(4, 4), NOTE_OFF(0, 70)))
            segment.add_event(MEVT(MT(0, 4), NOTE_ON(0, 60, 100)))
            segment.add_event(MEVT(MT(1, 4), NOTE_OFF(0, 60)))
            segment.add_event(MEVT(MT(1, 4), NOTE_ON(0, 61, 100)))
            segment.add_event(MEVT(MT(2, 4), NOTE_OFF(0, 61)))
            segment.add_event(MEVT(MT(2, 4), NOTE_ON(0, 62, 100)))
            segment.add_event(MEVT(MT(3, 4), NOTE_OFF(0, 62)))
            segment.add_event(MEVT(MT(3, 4), NOTE_ON(0, 63, 100)))
            segment.add_event(MEVT(MT(4, 4), NOTE_OFF(0, 63)))

        data = track.copy_segments([segment_ref])
        with self.project.apply_mutations('test'):
            segment_refs = track.paste_segments(data, MT(8, 4))

        self.assertEqual(len(segment_refs), 1)
        self.assertEqual(len(track.segments), 2)
        self.assertEqual(len(track.segment_heap), 2)
        self.assertEqual(segment_refs[0].time, MT(8, 4))

    async def test_link_segment(self):
        track = await self._add_track()
        with self.project.apply_mutations('test'):
            segment_ref = track.create_segment(MT(0, 4), MD(4, 4))
            segment = segment_ref.segment
            segment.add_event(MEVT(MT(0, 4), NOTE_ON(0, 70, 100)))
            segment.add_event(MEVT(MT(4, 4), NOTE_OFF(0, 70)))
            segment.add_event(MEVT(MT(0, 4), NOTE_ON(0, 60, 100)))
            segment.add_event(MEVT(MT(1, 4), NOTE_OFF(0, 60)))
            segment.add_event(MEVT(MT(1, 4), NOTE_ON(0, 61, 100)))
            segment.add_event(MEVT(MT(2, 4), NOTE_OFF(0, 61)))
            segment.add_event(MEVT(MT(2, 4), NOTE_ON(0, 62, 100)))
            segment.add_event(MEVT(MT(3, 4), NOTE_OFF(0, 62)))
            segment.add_event(MEVT(MT(3, 4), NOTE_ON(0, 63, 100)))
            segment.add_event(MEVT(MT(4, 4), NOTE_OFF(0, 63)))

        data = track.copy_segments([segment_ref])
        with self.project.apply_mutations('test'):
            segment_refs = track.link_segments(data, MT(8, 4))

        self.assertEqual(len(segment_refs), 1)
        self.assertEqual(len(track.segments), 2)
        self.assertEqual(len(track.segment_heap), 1)
        self.assertEqual(segment_refs[0].time, MT(8, 4))
        self.assertIs(segment_refs[0].segment, segment)

    async def test_connector(self):
        track = await self._add_track()

        messages = []
        def message_cb(msg):
            logging.info(msg)
            self.assertEqual(msg.node_id, track.pipeline_node_id)
            self.assertTrue(msg.HasExtension(processor_message_registry_pb2.pianoroll_mutation))
            mutation = msg.Extensions[processor_message_registry_pb2.pianoroll_mutation]
            messages.append(mutation.WhichOneof('mutation'))

        connector = track.create_node_connector(
            message_cb=message_cb, audioproc_client=None)
        try:
            messages.extend(connector.init())
            self.assertEqual(messages, [])

            messages.clear()
            with self.project.apply_mutations('test'):
                segment_ref = track.create_segment(MT(1, 4), MD(2, 4))
            self.assertEqual(messages, ['add_segment', 'add_segment_ref'])

            messages.clear()
            with self.project.apply_mutations('test'):
                segment_ref.time = MT(0, 4)
            self.assertEqual(messages, ['update_segment_ref'])

            messages.clear()
            with self.project.apply_mutations('test'):
                segment_ref.segment.duration = MD(3, 4)
            self.assertEqual(messages, ['update_segment'])

            messages.clear()
            with self.project.apply_mutations('test'):
                event = segment_ref.segment.add_event(MEVT(MT(1, 8), NOTE_ON(0, 64, 100)))
            self.assertEqual(messages, ['add_event'])

            messages.clear()
            with self.project.apply_mutations('test'):
                del segment_ref.segment.events[event.index]
            self.assertEqual(messages, ['remove_event'])

            messages.clear()
            with self.project.apply_mutations('test'):
                track.remove_segment(segment_ref)
            self.assertEqual(messages, ['remove_segment_ref', 'remove_segment'])

        finally:
            connector.cleanup()
