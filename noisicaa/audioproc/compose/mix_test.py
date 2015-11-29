#!/usr/bin/python3

import unittest

from ..pipeline import Pipeline
from ..exceptions import EndOfStreamError
from ..ports import AudioOutputPort
from . import mix

class FakeOutputPort(AudioOutputPort):
    def __init__(self, name, tracker, num):
        super().__init__(name)
        self.__tracker = tracker
        self.__num = num

    def get_frame(self, duration):
        if self.__num == 0:
            raise EndOfStreamError
        else:
            self.__num -= 1
            self.__tracker.append((self.name, duration))
            frame = self.create_frame(0)
            frame.resize(duration)
            return frame

    def start(self):
        pass


class MixTest(unittest.TestCase):
    def testBasicRun(self):
        pipeline = Pipeline()

        tracker = []
        source1 = FakeOutputPort('s1', tracker, 1)
        source2 = FakeOutputPort('s2', tracker, 2)
        source3 = FakeOutputPort('s3', tracker, 2)

        node = mix.Mix()
        pipeline.add_node(node)
        node.append_input(source1)
        node.append_input(source2)
        node.append_input(source3)
        node.setup()
        try:
            node.start()
            num_frames = 0
            while True:
                try:
                    node.run()
                    num_frames += 1
                except EndOfStreamError:
                    break
        finally:
            node.cleanup()

        self.assertEqual(num_frames, 1)
        self.assertEqual(
            tracker,
            [('s1', 4096), ('s2', 4096), ('s3', 4096)])


if __name__ == '__main__':
    unittest.main()
