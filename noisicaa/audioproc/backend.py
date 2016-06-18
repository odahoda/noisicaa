#!/usr/bin/python3

import logging
import threading

import pyaudio

from .resample import (Resampler,
                       AV_CH_LAYOUT_STEREO,
                       AV_SAMPLE_FMT_S16,
                       AV_SAMPLE_FMT_FLT)
from .node import Node
from .node_types import NodeType
from .ports import AudioInputPort, EventOutputPort
from .events import NoteOnEvent
from ..music.pitch import Pitch

logger = logging.getLogger(__name__)


class AudioSinkNode(Node):
    desc = NodeType()
    desc.name = 'audiosink'
    desc.port('in', 'input', 'audio')
    desc.is_system = True

    def __init__(self):
        super().__init__()

        self._input = AudioInputPort('in')
        self.add_input(self._input)

    def run(self, timepos):
        self.pipeline.backend.write(self._input.frame)


class MidiSourceNode(Node):
    desc = NodeType()
    desc.name = 'midisource'
    desc.port('out', 'output', 'events')
    desc.is_system = True

    def __init__(self):
        super().__init__()

        self._output = EventOutputPort('out')
        self.add_output(self._output)

    def run(self, timepos):
        self._output.events.clear()

        # TODO: real events from midi devices.
        self._output.events.append(NoteOnEvent(timepos, Pitch('C4')))


class Backend(object):
    def __init__(self):
        pass

    def setup(self):
        pass

    def cleanup(self):
        pass

    def wait(self):
        raise NotImplementedError

    def write(self, frame):
        raise NotImplementedError


class NullBackend(Backend):
    def wait(self):
        pass

    def write(self, frame):
        pass


class PyAudioBackend(Backend):
    def __init__(self):
        super().__init__()

        self._audio = None
        self._stream = None
        self._resampler = None
        self._buffer_lock = threading.Lock()
        self._buffer = bytearray()
        self._need_more = threading.Event()
        self._bytes_per_sample = 2 * 2
        self._buffer_threshold = 2048 * self._bytes_per_sample

    def setup(self):
        self._audio = pyaudio.PyAudio()

        ch_layout = AV_CH_LAYOUT_STEREO
        sample_fmt = AV_SAMPLE_FMT_S16
        sample_rate = 44100

        self._stream = self._audio.open(
            format=pyaudio.paInt16,
            channels=2,
            rate=sample_rate,
            output=True,
            stream_callback=self._callback)

        # use format of input buffer
        self._resampler = Resampler(
            AV_CH_LAYOUT_STEREO, AV_SAMPLE_FMT_FLT, 44100,
            ch_layout, sample_fmt, sample_rate)

        self._buffer.clear()
        self._need_more.set()

    def cleanup(self):
        if self._stream is not None:
            self._stream.close()
            self._stream = None

        if self._audio is not None:
            self._audio.terminate()
            self._audio = None

        self._resampler = None

    def _callback(self, in_data, frame_count, time_info, status):
        num_bytes = frame_count * self._bytes_per_sample
        with self._buffer_lock:
            samples = self._buffer[:num_bytes]
            del self._buffer[:num_bytes]

            if len(self._buffer) < self._buffer_threshold:
                self._need_more.set()

        if len(samples) < num_bytes:
            # buffer underrun, pad with silence
            logger.warning(
                "Buffer underrun, need %d samples, but only have %d",
                frame_count, len(samples) / self._bytes_per_sample)

            samples.extend([0] * (num_bytes - len(samples)))

        return (bytes(samples), pyaudio.paContinue)

    def wait(self):
        self._need_more.wait()

    def write(self, frame):
        samples = self._resampler.convert(frame.as_bytes(), len(frame))
        with self._buffer_lock:
            self._buffer.extend(samples)
            if len(self._buffer) >= self._buffer_threshold:
                self._need_more.clear()
