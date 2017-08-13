import enum
import logging
import os

import numpy

from libc cimport stdio
from libc cimport string
from libc cimport stdint


### LOGGING ###############################################################

# standard message
CSOUNDMSG_DEFAULT       = 0x0000
# error message (initerror, perferror, etc.)
CSOUNDMSG_ERROR         = 0x1000
# orchestra opcodes (e.g. printks)
CSOUNDMSG_ORCH          = 0x2000
# for progress display and heartbeat characters
CSOUNDMSG_REALTIME      = 0x3000
# warning messages
CSOUNDMSG_WARNING       = 0x4000

CSOUNDMSG_TYPE_MASK     = 0x7000

_logger = logging.getLogger('csound')
_logbuf = bytearray()

cdef void _message_callback(
        CSOUND* csnd, int attr, const char* fmt, va_list args) nogil:
    cdef char buf[10240]
    cdef int l
    l = vsnprintf(buf, sizeof(buf), fmt, args)

    with gil:
        try:
            _logbuf.extend(buf[:l])

            while True:
                eol = _logbuf.find(b'\n')
                if eol == -1:
                    break
                line = _logbuf[0:eol]
                del _logbuf[0:eol+1]

                line = line.decode('utf-8', 'replace')
                line = line.expandtabs(tabsize=8)

                if attr & CSOUNDMSG_TYPE_MASK == CSOUNDMSG_ERROR:
                    _logger.error('%s', line)
                elif attr & CSOUNDMSG_TYPE_MASK == CSOUNDMSG_WARNING:
                    _logger.warning('%s', line)
                else:
                    _logger.info('%s', line)
        except Exception as exc:
            _logger.exception("Exception in csound message callback:")
            os._exit(1)

csoundSetDefaultMessageCallback(_message_callback)


### GLOBAL INIT ###########################################################

CSOUNDINIT_NO_SIGNAL_HANDLER = 1
CSOUNDINIT_NO_ATEXIT = 2

csoundInitialize(CSOUNDINIT_NO_SIGNAL_HANDLER | CSOUNDINIT_NO_ATEXIT)


### CLIENT CODE ###########################################################

__version__ = '%d.%02d.%d' % (
    csoundGetVersion() // 1000,
    (csoundGetVersion() // 10) % 100,
    csoundGetVersion() % 10)


class CSoundError(Exception):
    pass


class ChannelType(enum.Enum):
    Control = 1
    Audio = 2
    String = 3
    Pvs = 4
    Var = 5

class Channel(object):
    def __init__(self, name, cs_type):
        self.name = name
        self.cs_type = cs_type

        self.type = {
            CSOUND_CONTROL_CHANNEL: ChannelType.Control,
            CSOUND_AUDIO_CHANNEL: ChannelType.Audio,
            CSOUND_STRING_CHANNEL: ChannelType.String,
            CSOUND_PVS_CHANNEL: ChannelType.Pvs,
            CSOUND_VAR_CHANNEL: ChannelType.Var,
        }[cs_type & CSOUND_CHANNEL_TYPE_MASK]
        self.is_input = bool(cs_type & CSOUND_INPUT_CHANNEL)
        self.is_output = bool(cs_type & CSOUND_OUTPUT_CHANNEL)

    def __str__(self):
        return '<Channel "%s" %s %s%s>' % (
            self.name, self.type.name.lower(),
            'in' if self.is_input else '',
            'out' if self.is_output else '')


cdef class CSound(object):
    def __cinit__(self):
        self.csnd = csoundCreate(NULL)

    def __dealloc__(self):
        if self.csnd != NULL:
            self.close()

    def __init__(self):
        self.channels = None
        self.initialized = False

        self._check(csoundSetOption(self.csnd, '-n'))

    def _check(self, rc):
        if rc < 0:
            raise CSoundError(rc)

    def set_orchestra(self, orc):
        assert not self.initialized

        if isinstance(orc, str):
            orc = orc.encode('utf-8')

        orc = b'sr=44100\n0dbfs=1\n' + orc
        self._check(csoundCompileOrc(self.csnd, orc))
        self._check(csoundStart(self.csnd))

        self.ksmps = csoundGetKsmps(self.csnd)

        self.channels = {}

        cdef controlChannelInfo_t* cinfo = NULL
        num = csoundListChannels(self.csnd, &cinfo)
        try:
            if num < 0:
                raise CSoundError(num)

            for idx in range(num):
                channel = Channel(
                    name=bytes(cinfo[idx].name).decode('utf-8'),
                    cs_type=cinfo[idx].type)
                self.channels[channel.name] = channel

        finally:
            if cinfo != NULL:
                csoundDeleteChannelList(self.csnd, cinfo)

        self.initialized = True

    def set_score(self, score):
        assert self.initialized

        if isinstance(score, str):
            score = score.encode('utf-8')
        self._check(csoundReadScore(self.csnd, score))

    def add_score_event(self, score):
        assert self.initialized

        if isinstance(score, str):
            score = score.encode('ascii')
        self._check(csoundReadScore(self.csnd, score))

    def perform(self):
        assert self.initialized

        cdef MYFLT* channel_dat
        for channel in self.channels.values():
            if not channel.is_output:
                continue
            self._check(csoundGetChannelPtr(
                self.csnd, &channel_dat,
                channel.name.encode('utf-8'), channel.cs_type))
            string.memset(channel_dat, 0, self.ksmps * sizeof(MYFLT))

        self._check(csoundPerformKsmps(self.csnd))

    def get_audio_channel_data(self, name):
        assert name in self.channels, name
        channel = self.channels[name]
        assert channel.is_output, channel
        assert channel.type == ChannelType.Audio, channel

        cdef MYFLT* channel_dat
        self._check(csoundGetChannelPtr(
            self.csnd, &channel_dat,
            channel.name.encode('utf-8'), channel.cs_type))

        out = bytearray(self.ksmps * sizeof(float))
        cdef int i = 0
        cdef float* outp = <float*><char*>out
        while i < self.ksmps:
            outp[i] = channel_dat[i]
            i += 1
        return out

    cdef int get_audio_channel_data_into(self, str name, float* out) except -1:
        assert name in self.channels, name
        channel = self.channels[name]
        assert channel.is_output, channel
        assert channel.type == ChannelType.Audio, channel

        cdef MYFLT* channel_dat
        self._check(csoundGetChannelPtr(
            self.csnd, &channel_dat,
            channel.name.encode('utf-8'), channel.cs_type))

        cdef int i = 0
        while i < self.ksmps:
            out[i] = channel_dat[i]
            i += 1
        return 0

    def set_audio_channel_data(self, name, samples):
        assert name in self.channels, name
        channel = self.channels[name]
        assert channel.is_input, channel
        assert channel.type == ChannelType.Audio, channel

        assert len(samples) == self.ksmps * sizeof(float)

        cdef MYFLT* channel_dat
        self._check(csoundGetChannelPtr(
            self.csnd, &channel_dat,
            channel.name.encode('utf-8'), channel.cs_type))

        cdef float* inp
        cdef char[:] view
        if isinstance(samples, memoryview):
            view = samples
            inp = <float*>(&view[0])
        elif isinstance(samples, (bytes, bytearray)):
            inp = <float*><char*>samples
        else:
            raise TypeError(type(samples))

        cdef int i
        for i in range(self.ksmps):
            channel_dat[i] = inp[i]

    def set_control_channel_value(self, name, value):
        assert name in self.channels, name
        channel = self.channels[name]
        assert channel.is_input, channel
        assert channel.type == ChannelType.Control, channel

        csoundSetControlChannel(
            self.csnd, channel.name.encode('utf-8'), value)

    def close(self):
        assert self.csnd != NULL
        csoundDestroy(self.csnd)
        self.csnd = NULL
