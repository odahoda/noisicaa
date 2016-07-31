#!/usr/bin/python3

class FrameData(object):
    def __init__(self):
        self.timepos = None
        self.samples = None
        self.num_samples = None
        self.events = None
        self.perf_data = None


class FrameContext(object):
    def __init__(self):
        self.timepos = None
        self.duration = None
        self.in_frame = None
        self.out_frame = None
        self.perf_stats = None

