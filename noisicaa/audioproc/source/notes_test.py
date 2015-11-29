#!/usr/bin/python3

import logging
import unittest

if __name__ == '__main__':
    import pyximport
    pyximport.install()

from . import notes
from noisicaa.music import Sheet, ScoreTrack


class NotesTest(unittest.TestCase):
    def testBasicRun(self):
        sheet = Sheet(name='test')
        track = ScoreTrack(name='test')
        sheet.tracks.append(track)
        node = notes.NoteSource(track)
        node.outputs['out'].connect()
        node.setup()
        try:
            node.start()
            for _ in range(100):
                node.run()
        finally:
            node.cleanup()


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
