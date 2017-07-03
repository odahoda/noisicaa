import enum
import logging
import os

import numpy

from libc cimport stdio
from libc cimport string
from libc cimport stdint

### DECLARATIONS ##########################################################

cdef extern from "stdarg.h" nogil:
    ctypedef int va_list

cdef extern from "stdio.h" nogil:
    int vsnprintf(char *str, size_t size, const char *fmt, va_list args)

cdef extern from "csound/csound.h" nogil:
    ctypedef int CSOUND
    ctypedef double MYFLT

    cdef enum CSOUND_STATUS:
        # Completed successfully.
        CSOUND_SUCCESS = 0
        # Unspecified failure.
        CSOUND_ERROR = -1
        # Failed during initialization.
        CSOUND_INITIALIZATION = -2
        # Failed during performance.
        CSOUND_PERFORMANCE = -3
        # Failed to allocate requested memory.
        CSOUND_MEMORY = -4
        # Termination requested by SIGINT or SIGTERM.
        CSOUND_SIGNAL = -5

    cdef enum controlChannelBehavior:
        CSOUND_CONTROL_CHANNEL_NO_HINTS = 0
        CSOUND_CONTROL_CHANNEL_INT      = 1
        CSOUND_CONTROL_CHANNEL_LIN      = 2
        CSOUND_CONTROL_CHANNEL_EXP      = 3

    ctypedef enum controlChannelType:
        CSOUND_CONTROL_CHANNEL = 1
        CSOUND_AUDIO_CHANNEL  = 2
        CSOUND_STRING_CHANNEL = 3
        CSOUND_PVS_CHANNEL = 4
        CSOUND_VAR_CHANNEL =  5

        CSOUND_CHANNEL_TYPE_MASK = 15

        CSOUND_INPUT_CHANNEL = 16
        CSOUND_OUTPUT_CHANNEL = 32

    ctypedef struct controlChannelHints_t:
       controlChannelBehavior behav
       MYFLT dflt
       MYFLT min
       MYFLT max
       int x
       int y
       int width
       int height
       char* attributes

    ctypedef struct controlChannelInfo_t:
        char* name
        int type
        controlChannelHints_t hints

    int csoundGetVersion()
    void csoundSetDefaultMessageCallback(
            void (*csoundMessageCallback_)(
                CSOUND*, int attr, const char* fmt, va_list args))

    void csoundInitialize(int)
    CSOUND* csoundCreate(void* hostdata)
    void csoundDestroy(CSOUND*)

    int csoundSetOption(CSOUND* csnd, char* option)
    int csoundCompileOrc(CSOUND* csnd, const char* orc)
    int csoundReadScore(CSOUND* csnd, const char* score)
    int csoundStart(CSOUND* csnd)
    void csoundStop(CSOUND* csnd)
    void csoundReset(CSOUND* csnd)
    int csoundPerformKsmps(CSOUND* csnd)
    stdint.uint32_t csoundGetNchnls(CSOUND* csnd)
    stdint.uint32_t csoundGetKsmps(CSOUND* csnd)
    MYFLT *csoundGetSpin(CSOUND* csnd)
    MYFLT *csoundGetSpout(CSOUND* csnd)
    MYFLT csoundGetScoreOffsetSeconds(CSOUND* csnd)

    int csoundListChannels(CSOUND* csnd, controlChannelInfo_t** lst)
    void csoundDeleteChannelList(CSOUND* csnd, controlChannelInfo_t* lst)
    int csoundGetChannelPtr(
        CSOUND* csnd, MYFLT** ptr, const char* name, int type)
    void csoundSetControlChannel(CSOUND* csnd, const char* name, MYFLT val)

    #MYFLT* csoundGetInputBuffer(CSOUND* csnd)
    #long csoundGetInputBufferSize(CSOUND* csnd)
    #MYFLT* csoundGetOutputBuffer(CSOUND* csnd)
    #long csoundGetOutputBufferSize(CSOUND* csnd)

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
    cdef CSOUND* csnd
    cdef readonly dict channels
    cdef readonly int ksmps
    cdef int initialized

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

        cdef int i = 0
        cdef float* inp = <float*><char*>samples
        while i < self.ksmps:
            channel_dat[i] = inp[i]
            i += 1

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
