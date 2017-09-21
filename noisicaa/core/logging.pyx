import logging

cdef void pylogging_cb(
    void* handle, const char* c_logger_name, LogLevel c_level, const char* c_msg) with gil:
    logger_name = bytes(c_logger_name).decode('utf-8')
    level = {
        LogLevel.DEBUG: logging.DEBUG,
        LogLevel.INFO: logging.INFO,
        LogLevel.WARNING: logging.WARNING,
        LogLevel.ERROR: logging.ERROR,
        }[c_level]
    msg = bytes(c_msg).decode('utf-8')

    logger = logging.getLogger(logger_name)
    logger.log(level, msg)


def init_pylogging():
    cdef LogSink* sink = new PyLogSink(NULL, pylogging_cb)
    LoggerRegistry.get_registry().set_sink(sink)

