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


class PianoRollTrackTest(base_track_test.TrackTestMixin, unittest.AsyncTestCase):
    node_uri = 'builtin://pianoroll-track'
    track_cls = model.PianoRollTrack

    async def test_create_segment(self):
        track = await self._add_track()
        self.assertEqual(len(track.segments), 0)
        self.assertEqual(len(track.segment_heap), 0)

        with self.project.apply_mutations('test'):
            segment_ref = track.create_segment(
                audioproc.MusicalTime(3, 4),
                audioproc.MusicalDuration(4, 4))
        self.assertEqual(segment_ref.time, audioproc.MusicalTime(3, 4))
        self.assertEqual(segment_ref.segment.duration, audioproc.MusicalDuration(4, 4))
        self.assertEqual(len(track.segments), 1)
        self.assertIs(track.segments[0], segment_ref)
        self.assertEqual(len(track.segment_heap), 1)
        self.assertIs(track.segment_heap[0], segment_ref.segment)

    async def test_remove_segment(self):
        track = await self._add_track()
        with self.project.apply_mutations('test'):
            segment_ref = track.create_segment(
                audioproc.MusicalTime(3, 4),
                audioproc.MusicalDuration(4, 4))

        with self.project.apply_mutations('test'):
            track.remove_segment(segment_ref)
        self.assertEqual(len(track.segments), 0)
        self.assertEqual(len(track.segment_heap), 0)

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
                segment_ref = track.create_segment(
                    audioproc.MusicalTime(1, 4),
                    audioproc.MusicalDuration(2, 4))
            self.assertEqual(messages, ['add_segment', 'add_segment_ref'])

            messages.clear()
            with self.project.apply_mutations('test'):
                segment_ref.time = audioproc.MusicalTime(0, 4)
            self.assertEqual(messages, ['update_segment_ref'])

            messages.clear()
            with self.project.apply_mutations('test'):
                segment_ref.segment.duration = audioproc.MusicalDuration(3, 4)
            self.assertEqual(messages, ['update_segment'])

            messages.clear()
            with self.project.apply_mutations('test'):
                event = segment_ref.segment.append_event(
                    value_types.MidiEvent(
                        audioproc.MusicalTime(1, 8),
                        bytes([0x90, 64, 100])))
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
