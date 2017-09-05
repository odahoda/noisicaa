#!/usr/bin/python3

import logging
import os
import os.path
import tempfile
import threading
import uuid

import capnp
import pyaudio

import noisicore
from .resample import (Resampler,
                       AV_CH_LAYOUT_STEREO,
                       AV_SAMPLE_FMT_S16,
                       AV_SAMPLE_FMT_FLT)

logger = logging.getLogger(__name__)

UNSET = object()


class Backend(object):
    def __init__(self):
        self.__stopped = threading.Event()
        self.__sample_rate = None
        self.__ctxt = None

    @property
    def ctxt(self):
        assert self.__ctxt is not None
        return self.__ctxt

    def setup(self, sample_rate):
        self.__sample_rate = sample_rate

    def cleanup(self):
        pass

    def set_parameters(self):
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
        self.__ctxt = ctxt

    def end_frame(self):
        self.__ctxt = None

    def output(self, channel, samples):
        raise NotImplementedError


class NullBackend(Backend):
    def __init__(self, parameters):
        super().__init__()
        self.__frame_size = 512

        self.set_parameters(**parameters)

    def set_parameters(self, *, frame_size=UNSET, **parameters):
        super().set_parameters(**parameters)

        if frame_size is not UNSET:
            self.__frame_size = frame_size

    def begin_frame(self, ctxt):
        super().begin_frame(ctxt)
        ctxt.perf.start_span('frame')
        ctxt.duration = self.__frame_size

    def end_frame(self):
        self.ctxt.perf.end_span()
        super().end_frame()

    def output(self, channel, samples):
        pass


class PyAudioBackend(Backend):
    def __init__(self, parameters):
        super().__init__()

        self.__audio = None
        self.__stream = None
        self.__resampler = None
        self.__buffer_lock = threading.Lock()
        self.__buffer = bytearray()
        self.__need_more = threading.Event()
        self.__bytes_per_sample = 2 * 2
        self.__buffer_threshold = 4096 * self.__bytes_per_sample
        self.__frame_size = 512
        self.__outputs = {}

        self.set_parameters(**parameters)

    def set_parameters(self, *, frame_size=UNSET, **parameters):
        super().set_parameters(**parameters)

        if frame_size is not UNSET:
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
        super().begin_frame(ctxt)
        if self.stopped:
            return
        self.__need_more.wait()
        ctxt.perf.start_span('frame')
        self.__outputs.clear()
        ctxt.duration = self.__frame_size

    def end_frame(self):
        self.ctxt.perf.end_span()

        # TODO: feed non-interleaved sample buffers directly into
        # resample
        interleaved = bytearray(8 * self.__frame_size)
        if 'left' in self.__outputs:
            interleaved[0::8] = self.__outputs['left'][0::4]
            interleaved[1::8] = self.__outputs['left'][1::4]
            interleaved[2::8] = self.__outputs['left'][2::4]
            interleaved[3::8] = self.__outputs['left'][3::4]
        else:
            logger.info("no left")

        if 'right' in self.__outputs:
            interleaved[4::8] = self.__outputs['right'][0::4]
            interleaved[5::8] = self.__outputs['right'][1::4]
            interleaved[6::8] = self.__outputs['right'][2::4]
            interleaved[7::8] = self.__outputs['right'][3::4]
        else:
            logger.info("no right")

        converted = self.__resampler.convert(interleaved, self.__frame_size)
        with self.__buffer_lock:
            self.__buffer.extend(converted)
            if len(self.__buffer) >= self.__buffer_threshold:
                self.__need_more.clear()

        super().end_frame()

    def output(self, channel, samples):
        self.__outputs[channel] = samples


class IPCBackend(Backend):
    def __init__(self, parameters, socket_dir=None):
        super().__init__()

        if socket_dir is None:
            socket_dir = tempfile.gettempdir()

        self.address = os.path.join(
            socket_dir, 'audiostream.%s.pipe' % uuid.uuid4().hex)

        self.__stream = noisicore.AudioStream.create_server(self.address)
        self.__out_frame = None
        self.__buffers = None

        self.set_parameters(**parameters)

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
        super().begin_frame(ctxt)

        try:
            in_frame = self.__stream.receive_block()
            ctxt.perf.start_span('frame')

            ctxt.duration = in_frame.blockSize
            ctxt.buffers = {
                buf.id: buf
                for buf in in_frame.buffers
            }
            ctxt.messages = in_frame.messages

            self.__out_frame = noisicore.BlockData.new_message()
            self.__out_frame.samplePos = in_frame.samplePos
            self.__out_frame.blockSize = in_frame.blockSize
            self.__buffers = []

        except noisicore.ConnectionClosed:
            logger.warning("Stopping IPC backend.")
            self.stop()

    def end_frame(self):
        if self.__out_frame is not None:
            self.ctxt.perf.end_span()

            self.__out_frame.init('buffers', len(self.__buffers))
            for idx, (id, data) in enumerate(self.__buffers):
                buf = self.__out_frame.buffers[idx]
                buf.id = id
                buf.data = data

            assert self.ctxt.perf.current_span_id == 0
            self.__out_frame.perfData = self.ctxt.perf.serialize()

            self.__stream.send_block(self.__out_frame)

        self.__out_frame = None
        self.__buffers = None

        super().end_frame()

    def output(self, channel, samples):
        assert self.__out_frame is not None

        self.__buffers.append(('output:%s' % channel, bytes(samples)))
