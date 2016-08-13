#!/usr/bin/python3

import logging
import collections
import functools
import operator

from .exceptions import Error
from .frame import Frame
from .audio_format import (AudioFormat,
                           CHANNELS_STEREO,
                           SAMPLE_FMT_FLT)

logger = logging.getLogger(__name__)


UNSET = object()


class Port(object):
    def __init__(self, name):
        self._name = name
        self.owner = None

    def __str__(self):
        return '<%s %s:%s>' % (
            type(self).__name__,
            self.owner.id if self.owner is not None else 'None',
            self.name)

    @property
    def name(self):
        return self._name

    @property
    def pipeline(self):
        return self.owner.pipeline

    def set_prop(self):
        pass


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
            assert port in self.inputs, port
            self.inputs.remove(port)

    def check_port(self, port):
        if not isinstance(port, OutputPort):
            raise Error("Can only connect to OutputPort")

    def collect_inputs(self):
        pass


class OutputPort(Port):
    def __init__(self, name):
        super().__init__(name)
        self._muted = False

    @property
    def muted(self):
        return self._muted

    @muted.setter
    def muted(self, value):
        self._muted = bool(value)

    def set_prop(self, muted=UNSET, **kwargs):
        super().set_prop(**kwargs)
        if muted is not UNSET:
            self.muted = muted


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
                self.frame.mul_add(
                    upstream_port.volume / 100.0, upstream_port.frame)


class AudioOutputPort(OutputPort):
    def __init__(self, name):
        super().__init__(name)
        # TODO: get sample_rate from pipeline
        self._audio_format = AudioFormat(CHANNELS_STEREO, SAMPLE_FMT_FLT, 44100)

        self.frame = Frame(self._audio_format, 0, set())
        self.frame.resize(4096)

        self._volume = 100

    @property
    def audio_format(self):
        return self._audio_format

    @property
    def volume(self):
        return self._volume

    @volume.setter
    def volume(self, value):
        value = float(value)
        if value < 0.0:
            raise ValueError("Invalid volume.")
        self._volume = float(value)

    def set_prop(self, volume=UNSET, **kwargs):
        super().set_prop(**kwargs)
        if volume is not UNSET:
            self.volume = volume


class EventInputPort(InputPort):
    def __init__(self, name):
        super().__init__(name)

        self.events = []

    def check_port(self, port):
        super().check_port(port)
        if not isinstance(port, EventOutputPort):
            raise Error("Can only connect to EventOutputPort")

    def collect_inputs(self):
        self.events.clear()
        for upstream_port in self.inputs:
            if not upstream_port.muted:
                self.events.extend(upstream_port.events)

        self.events.sort(key=lambda e: e.sample_pos)


class EventOutputPort(OutputPort):
    def __init__(self, name):
        super().__init__(name)

        self.events = []
