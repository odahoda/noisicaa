// -*- mode: c++ -*-

/*
 * @begin:license
 *
 * Copyright (c) 2015-2019, Benjamin Niemann <pink@odahoda.de>
 *
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation; either version 2 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License along
 * with this program; if not, write to the Free Software Foundation, Inc.,
 * 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
 *
 * @end:license
 */

#ifndef _NOISICAA_CORE_LOGGING_H
#define _NOISICAA_CORE_LOGGING_H

#include <map>
#include <memory>
#include <stdarg.h>

#include "noisicaa/core/pump.h"
#include "noisicaa/core/status.h"

namespace noisicaa {

using namespace std;

class LoggerRegistry;

enum LogLevel {
  DEBUG, INFO, WARNING, ERROR
};

static const size_t MaxLoggerNameLength = 128;

class LogSink {
public:
  virtual ~LogSink();

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

class RTSafePyLogSink : public LogSink {
public:
  typedef void (*callback_t)(void*, const char*, LogLevel, const char*);

  RTSafePyLogSink(void* handle, callback_t callback);

  void emit(const char* logger, LogLevel level, const char* msg) override;

  Status setup();
  void cleanup();

private:
  void* _handle;
  callback_t _callback;

  struct Block {
    char data[1024];
  };
  Pump<Block> _pump;

  uint32_t _seq = 0;

  struct LogRecordHeader {
    uint32_t magic;
    uint32_t seq;
    LogLevel level;
    char logger[MaxLoggerNameLength];
    size_t length;
    bool continued;
  };

  struct LogRecordContinuation {
    uint32_t magic;
    uint32_t seq;
    size_t length;
    bool continued;
  };

  LogRecordHeader _record;
  string _msg;
  void consume(Block block);
};

class Logger {
public:
  Logger(const char* name, LoggerRegistry* registry);

  const char* name() const { return _name; }

  void vlog(LogLevel level, const char* fmt, va_list args);
  void log(LogLevel level, const char* fmt, ...);
  void debug(const char* fmt, ...);
  void info(const char* fmt, ...);
  void warning(const char* fmt, ...);
  void error(const char* fmt, ...);

private:
  char _name[MaxLoggerNameLength];
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

  LogSink* sink() const { return _local_sink != nullptr ? _local_sink :_sink.get(); }

  // takes ownership of sink.
  void set_sink(LogSink* sink);

  // does not take ownership of sink.
  void set_threadlocal_sink(LogSink* sink);

private:
  static LoggerRegistry* _instance;
  static thread_local LogSink* _local_sink;

  Logger* _get_logger(const char* name);

  struct cmp_cstr {
    bool operator()(const char *a, const char *b);
  };
  map<const char*, unique_ptr<Logger>, cmp_cstr> _loggers;
  unique_ptr<LogSink> _sink;
};

}  // namespace noisicaa

#endif
