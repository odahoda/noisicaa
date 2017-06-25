#!/usr/bin/python3

import logging
import os
import os.path
import tempfile
import threading
import uuid

import capnp
import pyaudio

from .resample import (Resampler,
                       AV_CH_LAYOUT_STEREO,
                       AV_SAMPLE_FMT_S16,
                       AV_SAMPLE_FMT_FLT)
from . import audio_stream
from . import entity_capnp
from . import frame_data_capnp

logger = logging.getLogger(__name__)


class Backend(object):
    def __init__(self):
        self.__stopped = threading.Event()
        self.__event_queues = {}
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
        return self.__stopped.is_set()

    def stop(self):
        self.__stopped.set()

    def begin_frame(self, ctxt):
        raise NotImplementedError

    def end_frame(self):
        raise NotImplementedError

    def output(self, layout, num_samples, samples):
        raise NotImplementedError

    def clear_events(self):
        self.__event_queues.clear()

    def add_event(self, queue, event):
        self.__event_queues.setdefault(queue, []).append(event)

    def get_events(self, queue):
        return self.__event_queues.get(queue, [])

    def get_events_for_prefix(self, prefix):
        events = []

        for queue, qevents in self.__event_queues.items():
            if '/' not in queue:
                continue

            qprefix, qremainder = queue.split('/', 1)
            events.extend((qremainder, event) for event in qevents)

        events.sort(key=lambda e: e[1].sample_pos)
        return events


class NullBackend(Backend):
    def __init__(self, *, frame_size=512):
        super().__init__()
        self.__frame_size = frame_size

    def begin_frame(self, ctxt):
        ctxt.duration = self.__frame_size

    def end_frame(self):
        pass

    def output(self, layout, num_samples, samples):
        pass


class PyAudioBackend(Backend):
    def __init__(self, *, frame_size=512):
        super().__init__()

        self.__audio = None
        self.__stream = None
        self.__resampler = None
        self.__buffer_lock = threading.Lock()
        self.__buffer = bytearray()
        self.__need_more = threading.Event()
        self.__bytes_per_sample = 2 * 2
        self.__buffer_threshold = 4096 * self.__bytes_per_sample
        self.__frame_size = frame_size

    def setup(self, sample_rate):
        super().setup(sample_rate)

        self.__audio = pyaudio.PyAudio()

        ch_layout = AV_CH_LAYOUT_STEREO
        sample_fmt = AV_SAMPLE_FMT_S16
        sample_rate = 44100

        self.__stream = self.__audio.open(
            format=pyaudio.paInt16,
            channels=2,
            rate=sample_rate,
            output=True,
            stream_callback=self.__callback)

        # use format of input buffer
        self.__resampler = Resampler(
            AV_CH_LAYOUT_STEREO, AV_SAMPLE_FMT_FLT, self.sample_rate,
            ch_layout, sample_fmt, sample_rate)

        self.__buffer.clear()
        self.__need_more.set()

    def cleanup(self):
        if self.__stream is not None:
            self.__stream.close()
            self.__stream = None

        if self.__audio is not None:
            self.__audio.terminate()
            self.__audio = None

        self.__resampler = None

    def __callback(self, in_data, frame_count, time_info, status):
        num_bytes = frame_count * self.__bytes_per_sample
        with self.__buffer_lock:
            samples = self.__buffer[:num_bytes]
            del self.__buffer[:num_bytes]

            if len(self.__buffer) < self.__buffer_threshold:
                self.__need_more.set()

        if len(samples) < num_bytes:
            # buffer underrun, pad with silence
            logger.warning(
                "Buffer underrun, need %d samples, but only have %d",
                frame_count, len(samples) / self.__bytes_per_sample)

            samples.extend([0] * (num_bytes - len(samples)))

        return (bytes(samples), pyaudio.paContinue)

    def stop(self):
        super().stop()
        self.__need_more.set()

    def begin_frame(self, ctxt):
        if self.stopped:
            return
        self.__need_more.wait()
        self.clear_events()
        ctxt.duration = self.__frame_size

    def end_frame(self):
        pass

    def output(self, layout, num_samples, samples):
        assert layout == AV_CH_LAYOUT_STEREO

        # TODO: feed non-interleaved sample buffers directly into
        # resample
        interleaved = bytearray(8 * num_samples)
        interleaved[0::8] = samples[0][0::4]
        interleaved[1::8] = samples[0][1::4]
        interleaved[2::8] = samples[0][2::4]
        interleaved[3::8] = samples[0][3::4]
        interleaved[4::8] = samples[1][0::4]
        interleaved[5::8] = samples[1][1::4]
        interleaved[6::8] = samples[1][2::4]
        interleaved[7::8] = samples[1][3::4]

        converted = self.__resampler.convert(interleaved, num_samples)
        with self.__buffer_lock:
            self.__buffer.extend(converted)
            if len(self.__buffer) >= self.__buffer_threshold:
                self.__need_more.clear()


class IPCBackend(Backend):
    def __init__(self, socket_dir=None):
        super().__init__()

        if socket_dir is None:
            socket_dir = tempfile.gettempdir()

        self.address = os.path.join(
            socket_dir, 'audiostream.%s.pipe' % uuid.uuid4().hex)

        self.__stream = audio_stream.AudioStreamServer(self.address)
        self.__ctxt = None
        self.__out_frame = None

    def setup(self, sample_rate):
        super().setup(sample_rate)
        self.__stream.setup()

    def cleanup(self):
        self.__stream.cleanup()
        super().cleanup()

    def stop(self):
        self.__stream.close()
        super().stop()

    def begin_frame(self, ctxt):
        self.__ctxt = ctxt
        try:
            in_frame = self.__stream.receive_frame()
            ctxt.duration = in_frame.frameSize
            ctxt.entities = {
                entity.id: entity
                for entity in in_frame.entities
            }

            self.__out_frame = frame_data_capnp.FrameData.new_message()
            self.__out_frame.samplePos = in_frame.samplePos
            self.__out_frame.frameSize = in_frame.frameSize

        except audio_stream.StreamClosed:
            logger.warning("Stopping IPC backend.")
            self.stop()

    def end_frame(self):
        if self.__out_frame is not None:
            self.__stream.send_frame(self.__out_frame)

        self.clear_events()

        self.__out_frame = None
        self.__ctxt = None

    def output(self, layout, num_samples, samples):
        assert layout == AV_CH_LAYOUT_STEREO

        assert self.__out_frame is not None
        assert self.__ctxt.perf.current_span_id == 0

        perf_data = self.__ctxt.perf.get_spans()

        self.__out_frame.init('entities', 2)

        e = self.__out_frame.entities[0]
        e.id = 'output:left'
        e.type = entity_capnp.Entity.Type.audio
        e.size = 4 * num_samples
        e.data = bytes(samples[0])

        e = self.__out_frame.entities[1]
        e.id = 'output:right'
        e.type = entity_capnp.Entity.Type.audio
        e.size = 4 * num_samples
        e.data = bytes(samples[1])

        #self.__out_frame.perf_data = perf_data
