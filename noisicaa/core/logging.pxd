
cdef extern from "noisicaa/core/logging.h" namespace "noisicaa" nogil:
    enum LogLevel:
        DEBUG
        INFO
        WARNING
        ERROR

    cppclass LoggerRegistry

    cppclass Logger:
        Logger(const char* name, LoggerRegistry* registry)
        void log(LogLevel level, const char* fmt, ...)
        void debug(const char* fmt, ...)
        void info(const char* fmt, ...)
        void warning(const char* fmt, ...)
        void error(const char* fmt, ...)

    cppclass LogSink:
        void emit(const char* logger, LogLevel level, const char* msg)

    cppclass PyLogSink(LogSink):
        ctypedef void (*callback_t)(void*, const char*, LogLevel, const char*)

        PyLogSink(void* handle, callback_t callback)
        void emit(const char* logger, LogLevel level, const char* msg)

    cppclass LoggerRegistry:
        @staticmethod
        LoggerRegistry* get_registry()
        @staticmethod
        Logger* get_logger(const char* name)

        void set_sink(LogSink* sink)
