import logging
import os

from libc cimport stdio
from libc cimport string

### DECLARATIONS ##########################################################

cdef extern from "stdarg.h" nogil:
    ctypedef int va_list

cdef extern from "stdio.h" nogil:
    int vsnprintf(char *str, size_t size, const char *format, va_list ap)

cdef extern from "csound/csound.h" nogil:
    ctypedef int CSOUND;

    int csoundGetVersion()
    void csoundSetDefaultMessageCallback(
            void (*csoundMessageCallback_)(CSOUND*,
                                           int attr,
                                           const char* format,
                                           va_list))

    void csoundInitialize(int)
    void* csoundCreate(void_p)
    void csoundDestroy(void*)


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


cdef class CSound(object):
    cdef void* csnd

    def __cinit__(self):
        self.csnd = csoundCreate(None)

    def __dealloc__(self):
        if self.csnd != NULL:
            self.close()

    def close(self):
        assert self.csnd != NULL
        csoundDestroy(self.csnd)
        self.csnd = NULL
