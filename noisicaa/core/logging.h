// -*- mode: c++ -*-

#ifndef _NOISICORE_LOGGING_H
#define _NOISICORE_LOGGING_H

#include <map>
#include <memory>
#include <stdarg.h>

namespace noisicaa {

using namespace std;

class LoggerRegistry;

enum LogLevel {
  DEBUG, INFO, WARNING, ERROR
};

struct LogRecord {
  LogLevel level;
  size_t logger_length;
  size_t msg_length;
  char data[];
};

class LogSink {
public:
  ~LogSink();

  virtual void emit(const char* logger, LogLevel level, const char* msg) = 0;
};

class StdIOSink : public LogSink {
public:
  StdIOSink(FILE* fp);
  void emit(const char* logger, LogLevel level, const char* msg) override;

private:
  FILE* _fp;
};

class PyLogSink : public LogSink {
public:
  typedef void (*callback_t)(void*, const char*, LogLevel, const char*);

  PyLogSink(void* handle, callback_t callback);

  void emit(const char* logger, LogLevel level, const char* msg) override;

private:
  void* _handle;
  callback_t _callback;
};

class Logger {
public:
  static const size_t NAME_LENGTH = 128;

  Logger(const char* name, LoggerRegistry* registry);

  const char* name() const { return _name; }

  void vlog(LogLevel level, const char* fmt, va_list args);
  void log(LogLevel level, const char* fmt, ...);
  void debug(const char* fmt, ...);
  void info(const char* fmt, ...);
  void warning(const char* fmt, ...);
  void error(const char* fmt, ...);

private:
  char _name[NAME_LENGTH];
  LoggerRegistry* _registry;
};

class LoggerRegistry {
public:
  // You shouldn't create instances yourself, use get_registry() to get a singleton instance.
  // This constructor is only public for use by unittests.
  LoggerRegistry();

  static LoggerRegistry* get_registry();
  static void reset();

  static Logger* get_logger(const char* name) {
    return get_registry()->_get_logger(name);
  }

  LogSink* sink() const { return _sink.get(); }
  void set_sink(LogSink* sink);

private:
  static LoggerRegistry* _instance;

  Logger* _get_logger(const char* name);

  struct cmp_cstr {
    bool operator()(const char *a, const char *b);
  };
  map<const char*, unique_ptr<Logger>, cmp_cstr> _loggers;
  unique_ptr<LogSink> _sink;
};

}  // namespace noisicaa

#endif
