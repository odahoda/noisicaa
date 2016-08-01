#!/usr/bin/python3

import unittest

from . import project
from . import sheet
from . import score_track
from . import instrument


class SheetCommandTest(unittest.TestCase):
    def setUp(self):
        self.project = project.BaseProject()
        self.sheet = sheet.Sheet(name='Test', num_tracks=0)
        self.project.sheets.append(self.sheet)


class AddTrackTest(SheetCommandTest):
    def test_ok(self):
        cmd = sheet.AddTrack(track_type='score')
        self.project.dispatch_command(self.sheet.id, cmd)
        self.assertEqual(len(self.sheet.tracks), 1)


class DeleteTrackTest(SheetCommandTest):
    def test_ok(self):
        self.sheet.tracks.append(score_track.ScoreTrack(name='Test'))

        cmd = sheet.RemoveTrack(track=0)
        self.project.dispatch_command(self.sheet.id, cmd)
        self.assertEqual(len(self.sheet.tracks), 0)

    def test_track_with_instrument(self):
        self.sheet.tracks.append(score_track.ScoreTrack(name='Test'))
        self.sheet.tracks[0].instrument = instrument.SoundFontInstrument(
            name='Piano', path='/usr/share/sounds/sf2/FluidR3_GM.sf2',
            bank=0, preset=0)

        cmd = sheet.RemoveTrack(track=0)
        self.project.dispatch_command(self.sheet.id, cmd)
        self.assertEqual(len(self.sheet.tracks), 0)


if __name__ == '__main__':
    unittest.main()
