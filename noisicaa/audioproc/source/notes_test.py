#!/usr/bin/python3

import logging
import unittest

if __name__ == '__main__':
    import pyximport
    pyximport.install()

from noisicaa import music
from ..exceptions import EndOfStreamError
from . import notes


# class NotesTest(unittest.TestCase):
#     def testBasicRun(self):
#         project = music.BaseProject.make_demo()
#         node = notes.NoteSource(project.sheets[0].tracks[0])
#         node.setup()
#         try:
#             while True:
#                 try:
#                     node.run(0)
#                 except EndOfStreamError:
#                     break
#         finally:
#             node.cleanup()


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
