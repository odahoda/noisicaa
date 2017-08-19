from cpython.ref cimport PyObject
from libc cimport stdint

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


ctypedef enum ChannelType:
    Control = 1
    Audio = 2
    String = 3
    Pvs = 4
    Var = 5

cdef class Channel(object):
    cdef bytes _name
    cdef const char* cs_name
    cdef int cs_type
    cdef readonly ChannelType type
    cdef readonly int is_input
    cdef readonly int is_output

    @staticmethod
    cdef create(const char* name, int cs_type)

cdef class CSound(object):
    cdef CSOUND* csnd
    cdef int num_channels
    cdef PyObject** channel_list
    cdef readonly dict channels
    cdef readonly int ksmps
    cdef int initialized

    cdef int get_audio_channel_data_into(self, str name, float* out) except -1
