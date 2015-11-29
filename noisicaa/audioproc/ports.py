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
        self._input = None
        # TODO: get sample_rate from pipeline
        self._audio_format = AudioFormat(CHANNELS_STEREO, SAMPLE_FMT_FLT, 44100)

    @property
    def audio_format(self):
        return self._audio_format

    def connect(self, port):
        self.check_port(port)
        with self.pipeline.writer_lock():
            port.connect()
            self._input = port

    def disconnect(self):
        assert self._input is not None
        with self.pipeline.writer_lock():
            self._input.disconnect()
            self._input = None

    def check_port(self, port):
        if not isinstance(port, OutputPort):
            raise Error("Can only connect to OutputPort")
        if port.is_connected:
            raise Error("OutputPort is already connected")

    @property
    def is_connected(self):
        return self._input is not None

    @property
    def input(self):
        return self._input

    def start(self):
        if self._input:
            self._input.start()

    def stop(self):
        if self._input:
            self._input.stop()


class OutputPort(Port):
    def __init__(self, name):
        super().__init__(name)
        self._is_connected = False
        self._tag_listeners = []

    def add_tag_listener(self, listener):
        self._tag_listeners.append(listener)

    def notify_tag_listeners(self, tags):
        for listener in self._tag_listeners:
            listener(tags)

    @property
    def is_connected(self):
        return self._is_connected

    def connect(self):
        self._is_connected = True

    def disconnect(self):
        self._is_connected = False

    def start(self):
        self.owner.start()

    def stop(self):
        self.owner.stop()


class AudioInputPort(InputPort):
    def __init__(self, name):
        super().__init__(name)

    def check_port(self, port):
        super().check_port(port)
        if not isinstance(port, AudioOutputPort):
            raise Error("Can only connect to AudioOutputPort")
        if port.audio_format != self.audio_format:
            raise Error("OutputPort has mismatching audio format %s"
                        % port.audio_format)

    def get_frame(self, duration):
        with self.pipeline.reader_lock():
            return self._input.get_frame(duration)


class AudioOutputPort(OutputPort):
    def __init__(self, name):
        super().__init__(name)
        # TODO: get sample_rate from pipeline
        self._audio_format = AudioFormat(CHANNELS_STEREO, SAMPLE_FMT_FLT, 44100)

        self._buffered_duration = None
        self._buffer = None

        self._muted = False
        self._volume = 100

    @property
    def audio_format(self):
        return self._audio_format

    def start(self):
        self._buffer = collections.deque()
        self._buffered_duration = 0
        super().start()

    def stop(self):
        super().stop()
        self._buffer = None
        self._buffered_duration = None

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

    @property
    def buffered_duration(self):
        return self._buffered_duration

    def create_frame(self, timepos, tags=None):
        return Frame(self._audio_format, timepos, tags)

    def add_frame(self, frame):
        if not self._is_connected:
            return
        if self._buffered_duration is None:
            logger.error("AudioOutputPort.add_frame() but port is stopped.")
            return
        self._buffered_duration += len(frame)
        self._buffer.appendleft(frame)

    def get_frame(self, duration):
        if not self.owner.started:
            frame = self.create_frame(0)
            frame.resize(duration)
            return frame

        while self._buffered_duration < duration:
            try:
                self.owner.run()
            except EndOfStreamError:
                break

        if len(self._buffer) == 0:
            raise EndOfStreamError

        frame = None
        while duration > 0 and len(self._buffer) > 0:
            fr = self._buffer.pop()
            if len(fr) > duration:
                head = fr.pop(duration)
                self._buffer.append(fr)
                self._buffered_duration -= duration
                fr = head
            else:
                self._buffered_duration -= len(fr)

            if frame is None:
                frame = fr
            else:
                frame.append(fr)
            duration -= len(fr)

        assert frame is not None

        if self._muted:
            # Just throw away what we have and replace by silent frame of
            # same size.
            # Could be done more efficiently by clearing the current frame and
            # throw away the tags.
            duration = len(frame)
            frame = self.create_frame(frame.timepos)
            frame.resize(duration)
        elif self._volume != 100:
            frame.mul(self._volume / 100.0)

        if frame.tags:
            self.notify_tag_listeners(frame.tags)

        return frame

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
