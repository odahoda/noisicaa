#!/usr/bin/python3

import logging
import collections
import functools
import operator

from .exceptions import Error, EndOfStreamError
from .frame import Frame
from .audio_format import (AudioFormat,
                           CHANNELS_STEREO,
                           SAMPLE_FMT_FLT)

logger = logging.getLogger(__name__)


class Port(object):
    def __init__(self, name):
        self._name = name
        self.owner = None

    @property
    def name(self):
        return self._name

    @property
    def pipeline(self):
        return self.owner.pipeline


class InputPort(Port):
    def __init__(self, name):
        super().__init__(name)
        self.inputs = []

    def connect(self, port):
        self.check_port(port)
        with self.pipeline.writer_lock():
            self.inputs.append(port)

    def disconnect(self, port):
        with self.pipeline.writer_lock():
            assert port in self.inputs
            self.inputs.remove(port)

    def check_port(self, port):
        if not isinstance(port, OutputPort):
            raise Error("Can only connect to OutputPort")

    def collect_inputs(self):
        pass


class OutputPort(Port):
    def __init__(self, name):
        super().__init__(name)
        self._tag_listeners = []

    def add_tag_listener(self, listener):
        self._tag_listeners.append(listener)

    def notify_tag_listeners(self, tags):
        for listener in self._tag_listeners:
            listener(tags)


class AudioInputPort(InputPort):
    def __init__(self, name):
        super().__init__(name)

        # TODO: get sample_rate from pipeline
        self._audio_format = AudioFormat(CHANNELS_STEREO, SAMPLE_FMT_FLT, 44100)
        self.frame = Frame(self._audio_format, 0, set())
        self.frame.resize(4096)

    @property
    def audio_format(self):
        return self._audio_format

    def check_port(self, port):
        super().check_port(port)
        if not isinstance(port, AudioOutputPort):
            raise Error("Can only connect to AudioOutputPort")
        if port.audio_format != self.audio_format:
            raise Error("OutputPort has mismatching audio format %s"
                        % port.audio_format)

    def collect_inputs(self):
        self.frame.clear()
        for upstream_port in self.inputs:
            if not upstream_port.muted:
                self.frame.add(upstream_port.frame)


class AudioOutputPort(OutputPort):
    def __init__(self, name):
        super().__init__(name)
        # TODO: get sample_rate from pipeline
        self._audio_format = AudioFormat(CHANNELS_STEREO, SAMPLE_FMT_FLT, 44100)

        self.frame = Frame(self._audio_format, 0, set())
        self.frame.resize(4096)

        self._muted = False
        self._volume = 100

    @property
    def audio_format(self):
        return self._audio_format

    @property
    def muted(self):
        return self._muted

    @muted.setter
    def muted(self, value):
        self._muted = bool(value)

    @property
    def volume(self):
        return self._volume

    @volume.setter
    def volume(self, value):
        value = float(value)
        if value < 0.0:
            raise ValueError("Invalid volume.")
        self._volume = float(value)


class EventInputPort(InputPort):
    def __init__(self, name):
        super().__init__(name)

    def check_port(self, port):
        super().check_port(port)
        if not isinstance(port, EventOutputPort):
            raise Error("Can only connect to EventOutputPort")

    def get_events(self, duration):
        with self.pipeline.reader_lock():
            return self._input.get_events(duration)


class EventOutputPort(OutputPort):
    def __init__(self, name):
        super().__init__(name)

        self._buffer = None
        self._latest_timepos = None

    def start(self):
        self._buffer = collections.deque()
        self._latest_timepos = 0
        super().start()

    def stop(self):
        super().stop()
        self._buffer = None
        self._latest_timepos = None

    def get_events(self, duration):
        if not self.owner.started:
            return []

        self.owner.run()
        events = list(self._buffer)
        self._buffer.clear()

        tags = functools.reduce(
            operator.__or__, (event.tags for event in events), set())
        if tags:
            self.notify_tag_listeners(tags)
        return events

    def add_event(self, event):
        assert event.timepos >= self._latest_timepos
        self._buffer.append(event)
        self._latest_timepos = event.timepos
