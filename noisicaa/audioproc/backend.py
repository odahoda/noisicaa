#!/usr/bin/python3

import logging
import os
import os.path
import pickle
import queue
import random
import select
import tempfile
import threading
import time
import uuid

import pyaudio

from .resample import (Resampler,
                       AV_CH_LAYOUT_STEREO,
                       AV_SAMPLE_FMT_S16,
                       AV_SAMPLE_FMT_FLT)
from .node import Node
from .node_types import NodeType
from .ports import AudioInputPort, EventOutputPort
from . import events
from .. import music
from . import audio_format
from . import frame
from . import audio_stream

logger = logging.getLogger(__name__)


class AudioSinkNode(Node):
    desc = NodeType()
    desc.name = 'audiosink'
    desc.port('in', 'input', 'audio')
    desc.is_system = True

    def __init__(self, event_loop):
        super().__init__(event_loop, id='sink')

        self._input = AudioInputPort('in')
        self.add_input(self._input)

    def run(self, timepos):
        self.pipeline.backend.write(self._input.frame)


class SystemEventSourceNode(Node):
    desc = NodeType()
    desc.name = 'systemeventsource'
    desc.port('out', 'output', 'events')
    desc.is_system = True

    def __init__(self, event_loop):
        super().__init__(event_loop)

        self._output = EventOutputPort('out')
        self.add_output(self._output)

    def run(self, timepos):
        self._output.events.clear()


class Backend(object):
    def __init__(self):
        self._stopped = threading.Event()
        self._event_queues = {}

    def setup(self):
        pass

    def cleanup(self):
        pass

    @property
    def stopped(self):
        return self._stopped.is_set()

    def stop(self):
        self._stopped.set()

    def wait(self, timepos):
        raise NotImplementedError

    def write(self, frame):
        raise NotImplementedError

    def clear_events(self):
        self._event_queues.clear()

    def add_event(self, queue, event):
        logger.info("Event %s for queue %s", event, queue)
        self._event_queues.setdefault(queue, []).append(event)

    def get_events(self, queue):
        return self._event_queues.get(queue, [])

    def get_events_for_prefix(self, prefix):
        events = []

        for queue, qevents in self._event_queues.items():
            if '/' not in queue:
                continue

            qprefix, qremainder = queue.split('/', 1)
            events.extend((qremainder, event) for event in qevents)

        events.sort(key=lambda e: e[1].timepos)
        return events


class NullBackend(Backend):
    def wait(self, timepos):
        time.sleep(0.01)

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

    def stop(self):
        super().stop()
        self._need_more.set()

    def wait(self, timepos):
        if self.stopped:
            return
        self._need_more.wait()

    def write(self, frame):
        samples = self._resampler.convert(frame.as_bytes(), len(frame))
        with self._buffer_lock:
            self._buffer.extend(samples)
            if len(self._buffer) >= self._buffer_threshold:
                self._need_more.clear()


class Stopped(Exception):
    pass


class IPCBackend(Backend):
    def __init__(self, socket_dir=None):
        super().__init__()

        if socket_dir is None:
            socket_dir = tempfile.gettempdir()

        self.address = os.path.join(
            socket_dir, 'audiostream.%s.pipe' % uuid.uuid4().hex)

        self._stream = audio_stream.AudioStreamServer(self.address)
        self._timepos = None

    def setup(self):
        super().setup()
        self._stream.setup()

    def cleanup(self):
        self._stream.cleanup()
        super().cleanup()

    def stop(self):
        self._stream.close()
        super().stop()

    def wait(self, timepos):
        try:
            data = self._stream.receive_frame()
            self._timepos = data.timepos
            for queue, event in data.events:
                # Correct event's timepos.
                if event.timepos != -1:
                    event.timepos -= self._timepos - timepos
                self.add_event(queue, event)

        except audio_stream.StreamClosed:
            self.stop()

    def write(self, frame):
        data = audio_stream.FrameData()
        data.timepos = self._timepos
        data.samples = frame.as_bytes()
        data.num_samples = len(frame)
        self._stream.send_frame(data)
