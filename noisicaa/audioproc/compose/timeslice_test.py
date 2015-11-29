#!/usr/bin/python3

import unittest

from ..pipeline import Pipeline
from ..exceptions import EndOfStreamError
from ..ports import AudioOutputPort
from . import timeslice

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


class TimeSliceTest(unittest.TestCase):
    def testBasicRun(self):
        pipeline = Pipeline()

        tracker = []
        source1 = FakeOutputPort('s1', tracker, 3)

        node = timeslice.TimeSlice(4196)
        pipeline.add_node(node)
        node.inputs['in'].connect(source1)
        node.outputs['out'].connect()
        node.setup()
        try:
            node.outputs['out'].start()
            num_frames = 0
            while True:
                try:
                    node.run()
                    num_frames += 1
                except EndOfStreamError:
                    break
        finally:
            node.cleanup()

        self.assertEqual(num_frames, 2)
        self.assertEqual(node.outputs['out'].buffered_duration, 4196)
        self.assertEqual(
            tracker,
            [('s1', 4096), ('s1', 100)])


if __name__ == '__main__':
    unittest.main()
