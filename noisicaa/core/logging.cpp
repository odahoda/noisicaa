/*
 * @begin:license
 *
 * Copyright (c) 2015-2018, Benjamin Niemann <pink@odahoda.de>
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

#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "noisicaa/core/logging.h"

namespace noisicaa {

LogSink::~LogSink() {}

StdIOSink::StdIOSink(FILE* fp)
  : _fp(fp) {}

void StdIOSink::emit(const char* logger, LogLevel level, const char* msg) {
  // TODO: make this thread safe
  switch (level) {
  case LogLevel::DEBUG:   fwrite("DEBUG:", 1, 6, _fp);   break;
  case LogLevel::INFO:    fwrite("INFO:", 1, 5, _fp);    break;
  case LogLevel::WARNING: fwrite("WARNING:", 1, 8, _fp); break;
  case LogLevel::ERROR:   fwrite("ERROR:", 1, 6, _fp);   break;
  }

  fwrite(logger, 1, strlen(logger), _fp);
  fwrite(":", 1, 1, _fp);
  fwrite(msg, 1, strlen(msg), _fp);
  fwrite("\n", 1, 1, _fp);
  fflush(_fp);
}

PyLogSink::PyLogSink(void* handle, callback_t callback)
  : _handle(handle),
    _callback(callback) {}

void PyLogSink::emit(const char* logger, LogLevel level, const char* msg) {
  _callback(_handle, logger, level, msg);
}

Logger::Logger(const char* name, LoggerRegistry* registry)
  : _registry(registry) {
  assert(strlen(name) < NAME_LENGTH - 1);
  strncpy(_name, name, NAME_LENGTH);
}

void Logger::vlog(LogLevel level, const char* fmt, va_list args) {
  char msg[10000];
  vsnprintf(msg, sizeof(msg), fmt, args);
  _registry->sink()->emit(_name, level, msg);
}

void Logger::log(LogLevel level, const char* fmt, ...) {
  va_list args;
  va_start(args, fmt);
  vlog(level, fmt, args);
  va_end(args);
}

void Logger::debug(const char* fmt, ...) {
  va_list args;
  va_start(args, fmt);
  vlog(LogLevel::DEBUG, fmt, args);
  va_end(args);
}

void Logger::info(const char* fmt, ...) {
  va_list args;
  va_start(args, fmt);
  vlog(LogLevel::INFO, fmt, args);
  va_end(args);
}

void Logger::warning(const char* fmt, ...) {
  va_list args;
  va_start(args, fmt);
  vlog(LogLevel::WARNING, fmt, args);
  va_end(args);
}

void Logger::error(const char* fmt, ...) {
  va_list args;
  va_start(args, fmt);
  vlog(LogLevel::ERROR, fmt, args);
  va_end(args);
}

LoggerRegistry::LoggerRegistry() {}

LoggerRegistry* LoggerRegistry::_instance = nullptr;

LoggerRegistry* LoggerRegistry::get_registry() {
  // TODO: make this thread safe
  if (_instance == nullptr) {
    _instance = new LoggerRegistry();
  }

  return _instance;
}

Logger* LoggerRegistry::_get_logger(const char *name) {
  const auto& it = _loggers.find(name);
  if (it != _loggers.end()) {
    return it->second.get();
  }

  if (_sink.get() == nullptr) {
    _sink.reset(new StdIOSink(stderr));
  }

  Logger* logger = new Logger(name, this);
  _loggers.emplace(logger->name(), unique_ptr<Logger>(logger));
  return logger;
}

void LoggerRegistry::set_sink(LogSink* sink) {
  _sink.reset(sink);
}

bool LoggerRegistry::cmp_cstr::operator()(const char *a, const char *b) {
  return strcmp(a, b) < 0;
}

}
