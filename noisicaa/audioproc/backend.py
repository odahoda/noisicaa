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

from noisicaa import music
from noisicaa import core
from noisicaa import node_db

from .resample import (Resampler,
                       AV_CH_LAYOUT_STEREO,
                       AV_SAMPLE_FMT_S16,
                       AV_SAMPLE_FMT_FLT)
from .node import Node
from .ports import AudioInputPort, EventOutputPort
from . import events
from . import audio_format
from . import frame
from . import audio_stream
from . import data

logger = logging.getLogger(__name__)


class AudioSinkNode(Node):
    class_name = 'audiosink'

    def __init__(self, event_loop):
        description = node_db.SystemNodeDescription(
            ports=[
                node_db.AudioPortDescription(
                    name='in',
                    direction=node_db.PortDirection.Input,
                    channels='stereo'),
            ])

        super().__init__(event_loop, description, id='sink')

    def run(self, ctxt):
        input_port = self.inputs['in']

        ctxt.out_frame = data.FrameData()
        ctxt.out_frame.sample_pos = ctxt.sample_pos
        ctxt.out_frame.duration = ctxt.duration
        ctxt.out_frame.samples = input_port.frame.as_bytes()
        ctxt.out_frame.num_samples = len(input_port.frame)


class SystemEventSourceNode(Node):
    class_name = 'systemeventsource'

    def __init__(self, event_loop):
        description = node_db.SystemNodeDescription(
            ports=[
                node_db.EventPortDescription(
                    name='out',
                    direction=node_db.PortDirection.Output),
            ])

        super().__init__(event_loop, description)

    def run(self, ctxt):
        output_port = self.outputs['out']
        output_port.events.clear()


class Backend(object):
    def __init__(self):
        self._stopped = threading.Event()
        self._event_queues = {}
        self.__sample_rate = None

    def setup(self, sample_rate):
        self.__sample_rate = sample_rate

    def cleanup(self):
        pass

    @property
    def sample_rate(self):
        return self.__sample_rate

    @property
    def stopped(self):
        return self._stopped.is_set()

    def stop(self):
        self._stopped.set()

    def wait(self, ctxt):
        raise NotImplementedError

    def write(self, ctxt):
        raise NotImplementedError

    def clear_events(self):
        self._event_queues.clear()

    def add_event(self, queue, event):
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

        events.sort(key=lambda e: e[1].sample_pos)
        return events


class NullBackend(Backend):
    def wait(self, sample_pos):
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
        self._buffer_threshold = 4096 * self._bytes_per_sample

    def setup(self, sample_rate):
        super().setup(sample_rate)

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
            AV_CH_LAYOUT_STEREO, AV_SAMPLE_FMT_FLT, self.sample_rate,
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

    def wait(self, ctxt):
        if self.stopped:
            return
        self._need_more.wait()

    def write(self, ctxt):
        assert ctxt.out_frame is not None
        assert ctxt.out_frame.samples is not None
        assert ctxt.out_frame.num_samples > 0
        samples = self._resampler.convert(
            ctxt.out_frame.samples, ctxt.out_frame.num_samples)
        with self._buffer_lock:
            self._buffer.extend(samples)
            if len(self._buffer) >= self._buffer_threshold:
                self._need_more.clear()
        self.clear_events()


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
        self._sample_pos_offset = None

    def setup(self, sample_rate):
        super().setup(sample_rate)
        self._stream.setup()

    def cleanup(self):
        self._stream.cleanup()
        super().cleanup()

    def stop(self):
        self._stream.close()
        super().stop()

    def wait(self, ctxt):
        try:
            ctxt.in_frame = self._stream.receive_frame()
            ctxt.duration = ctxt.in_frame.duration
            self.sample_pos_offset = ctxt.in_frame.sample_pos - ctxt.sample_pos
            ctxt.in_frame.sample_pos = ctxt.sample_pos
            for queue, event in ctxt.in_frame.events:
                # Correct event's sample_pos.
                if event.sample_pos != -1:
                    event.sample_pos -= self.sample_pos_offset
                self.add_event(queue, event)

        except audio_stream.StreamClosed:
            logger.warning("Stopping IPC backend.")
            self.stop()

    def write(self, ctxt):
        assert ctxt.out_frame is not None
        assert ctxt.perf.current_span_id == 0

        perf_data = ctxt.perf.get_spans()

        ctxt.out_frame.sample_pos += self.sample_pos_offset
        ctxt.out_frame.perf_data = perf_data
        self._stream.send_frame(ctxt.out_frame)
        self.clear_events()
