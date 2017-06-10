#!/usr/bin/python3

import pickle

import numpy

from .vm import buffer_type


class Entity(object):
    def __init__(self):
        pass

    @classmethod
    def deserialize(self, serialized):
        return pickle.loads(serialized)

    def serialize(self):
        return pickle.dumps(self)

    def copy_to_buffer(self, buf):
        raise NotImplementedError


class ControlFrameEntity(Entity):
    def __init__(self):
        super().__init__()
        self.frame = numpy.array([], dtype=numpy.float32)

    def append(self, frame):
        r1 = len(self.frame)
        r2 = r1 + len(frame)
        self.frame.resize(r2)
        self.frame[r1:r2] = frame


class AudioFrameEntity(Entity):
    def __init__(self, channels):
        super().__init__()
        self.frame = numpy.ndarray(shape=(0, channels), dtype=numpy.float32)

    def append(self, frame):
        assert len(frame.shape) == 2
        assert frame.shape[1] == self.frame.shape[1]
        r1 = len(self.frame)
        r2 = r1 + len(frame)
        self.frame.resize((r2, self.frame.shape[1]))
        self.frame[r1:r2] = frame


class AtomEntity(Entity):
    size = 10240

    def __init__(self):
        super().__init__()
        self.buf = bytearray(self.size)

    def copy_to_buffer(self, buf):
        assert isinstance(buf.type, buffer_type.AtomData), str(buf.type)
        buf.set_bytes(self.buf)


class FrameData(object):
    def __init__(self):
        self.sample_pos = None
        self.duration = None
        self.samples = None
        self.num_samples = None
        self.events = None
        self.perf_data = None
        self.entities = None


class FrameContext(object):
    def __init__(self):
        self.sample_pos = None
        self.duration = None
        self.entities = None
        self.perf_stats = None

