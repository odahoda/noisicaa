#!/usr/bin/python3

import pickle

class Entity(object):
    def __init__(self):
        pass

    @classmethod
    def deserialize(self, serialized):
        return pickle.loads(serialized)

    def serialize(self):
        return pickle.dumps(self)


class ControlFrameEntity(Entity):
    def __init__(self):
        super().__init__()
        self.frame = None


class AudioFrameEntity(Entity):
    def __init__(self):
        super().__init__()
        self.frame = None


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
        self.in_frame = None
        self.out_frame = None
        self.perf_stats = None

