from cpython.ref cimport PyObject
from cpython.mem cimport PyMem_Malloc, PyMem_Free
from libc cimport stdio
from libc cimport string
from libc cimport stdint

import enum
import logging
import os


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


cdef class Channel(object):
    def __init__(self):
        raise RuntimeError("Class cannot be instatiated from Python")

    @staticmethod
    cdef create(const char* name, int cs_type):
        cdef Channel self = Channel.__new__(Channel)

        self._name = bytes(name)
        self.cs_name = <char*>self._name
        self.cs_type = cs_type

        self.type = {
            CSOUND_CONTROL_CHANNEL: ChannelType.Control,
            CSOUND_AUDIO_CHANNEL: ChannelType.Audio,
            CSOUND_STRING_CHANNEL: ChannelType.String,
            CSOUND_PVS_CHANNEL: ChannelType.Pvs,
            CSOUND_VAR_CHANNEL: ChannelType.Var,
        }[cs_type & CSOUND_CHANNEL_TYPE_MASK]
        self.is_input = 1 if cs_type & CSOUND_INPUT_CHANNEL else 0
        self.is_output = 1 if cs_type & CSOUND_OUTPUT_CHANNEL else 0

        return self

    @property
    def name(self):
        return self._name.decode('utf-8')

    @property
    def type_name(self):
        if self.type == ChannelType.Control:
            return 'control'
        elif self.type == ChannelType.Audio:
            return 'audio'
        elif self.type == ChannelType.String:
            return 'string'
        elif self.type == ChannelType.Pvs:
            return 'pvs'
        elif self.type == ChannelType.Var:
            return 'var'
        else:
            raise ValueError(self.type)

    def __str__(self):
        return '<Channel "%s" %s %s%s>' % (
            self.name, self.type_name,
            'in' if self.is_input else '',
            'out' if self.is_output else '')


cdef int _check(int rc) nogil except -1:
    if rc < 0:
        with gil:
            raise CSoundError(rc)
    return rc


cdef class CSound(object):
    def __cinit__(self):
        self.csnd = csoundCreate(NULL)

    def __dealloc__(self):
        if self.csnd != NULL:
            self.close()

    def __init__(self):
        self.channels = None
        self.initialized = False

        _check(csoundSetOption(self.csnd, '-n'))

    def set_orchestra(self, orc):
        assert not self.initialized

        if isinstance(orc, str):
            orc = orc.encode('utf-8')

        orc = b'sr=44100\n0dbfs=1\n' + orc
        _check(csoundCompileOrc(self.csnd, orc))
        _check(csoundStart(self.csnd))

        self.ksmps = csoundGetKsmps(self.csnd)

        if self.channel_list != NULL:
            PyMem_Free(self.channel_list)
            self.channel_list = NULL

        cdef controlChannelInfo_t* cinfo = NULL
        try:
            self.num_channels = _check(csoundListChannels(self.csnd, &cinfo))

            self.channels = {}
            self.channel_list = <PyObject**>PyMem_Malloc(self.num_channels * sizeof(PyObject*))

            for idx in range(self.num_channels):
                channel = Channel.create(cinfo[idx].name, cinfo[idx].type)
                self.channels[channel.name] = channel
                self.channel_list[idx] = <PyObject*>channel

        finally:
            if cinfo != NULL:
                csoundDeleteChannelList(self.csnd, cinfo)

        self.initialized = True

    def set_score(self, score):
        assert self.initialized

        if isinstance(score, str):
            score = score.encode('utf-8')
        _check(csoundReadScore(self.csnd, score))

    def add_score_event(self, score):
        assert self.initialized

        if isinstance(score, str):
            score = score.encode('ascii')
        _check(csoundReadScore(self.csnd, score))

    def perform(self):
        cdef:
            MYFLT* channel_dat
            PyObject* channel
            int idx

        with nogil:
            if not self.initialized:
                with gil:
                    raise AssertionError

            for idx in range(self.num_channels):
                channel = self.channel_list[idx]
                if not (<Channel>channel).is_output:
                    continue
                _check(csoundGetChannelPtr(
                    self.csnd, &channel_dat,
                    (<Channel>channel).cs_name, (<Channel>channel).cs_type))
                string.memset(channel_dat, 0, self.ksmps * sizeof(MYFLT))

            _check(csoundPerformKsmps(self.csnd))

    def get_audio_channel_data(self, name):
        assert name in self.channels, name
        cdef Channel channel = self.channels[name]
        assert channel.is_output, channel
        assert channel.type == ChannelType.Audio, channel

        cdef MYFLT* channel_dat
        _check(csoundGetChannelPtr(
            self.csnd, &channel_dat, channel.cs_name, channel.cs_type))

        out = bytearray(self.ksmps * sizeof(float))
        cdef int i = 0
        cdef float* outp = <float*><char*>out
        while i < self.ksmps:
            outp[i] = channel_dat[i]
            i += 1
        return out

    cdef int get_audio_channel_data_into(self, str name, float* out) except -1:
        cdef:
            Channel channel
            MYFLT* channel_dat
            int i

        channel = self.channels[name]
        with nogil:
            if not channel.is_output:
                with gil:
                    raise TypeError("Channel %s is not an output channel" % channel)
            if channel.type != ChannelType.Audio:
                with gil:
                    raise TypeError("Channel %s is not an audio channel" % channel)

            _check(csoundGetChannelPtr(
                self.csnd, &channel_dat, channel.cs_name, channel.cs_type))

            for i in range(self.ksmps):
                out[i] = channel_dat[i]
            return 0

    def set_audio_channel_data(self, name, samples):
        assert name in self.channels, name
        cdef Channel channel = self.channels[name]
        assert channel.is_input, channel
        assert channel.type == ChannelType.Audio, channel

        assert len(samples) == self.ksmps * sizeof(float)

        cdef MYFLT* channel_dat
        _check(csoundGetChannelPtr(
            self.csnd, &channel_dat, channel.cs_name, channel.cs_type))

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
        cdef Channel channel = self.channels[name]
        assert channel.is_input, channel
        assert channel.type == ChannelType.Control, channel

        csoundSetControlChannel(self.csnd, channel.cs_name, value)

    def close(self):
        if self.channel_list != NULL:
            PyMem_Free(self.channel_list)
            self.channel_list = NULL
            self.channels = {}

        if self.csnd != NULL:
            csoundDestroy(self.csnd)
            self.csnd = NULL
