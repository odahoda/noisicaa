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

#include <assert.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include "noisicaa/core/logging.h"
#include "noisicaa/core/pump.inl.h"
#include "noisicaa/audioproc/engine/rtcheck.h"

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
  // In unittests engine code calls directly into the PyLogSink, not using the RTSafePyLogSink. So
  // not complain about any RT violations.
  RTUnsafe rtu;
  _callback(_handle, logger, level, msg);
}

RTSafePyLogSink::RTSafePyLogSink(void* handle, callback_t callback)
  : _handle(handle),
    _callback(callback),
    _pump(nullptr, bind(&RTSafePyLogSink::consume, this, placeholders::_1)) {}

Status RTSafePyLogSink::setup() {
  RETURN_IF_ERROR(_pump.setup());
  return Status::Ok();
}

void RTSafePyLogSink::cleanup() {
  _pump.cleanup();
}

void RTSafePyLogSink::emit(const char* logger, LogLevel level, const char* msg) {
  Block block;

  size_t length = strlen(msg);
  if (length == 0) {
    return;
  }

  LogRecordHeader* header = (LogRecordHeader*)block.data;
  header->magic = 0x87b6c23a;
  header->seq = _seq++;
  header->level = level;
  strncpy(header->logger, logger, MaxLoggerNameLength);
  header->length = min(length, 1024 - sizeof(LogRecordHeader));
  memcpy(block.data + sizeof(LogRecordHeader), msg, header->length);
  msg += header->length;
  length -= header->length;
  header->continued = (length > 0);
  _pump.push(block);

  while (length > 0) {
    LogRecordContinuation* cont = (LogRecordContinuation*)block.data;
    cont->magic = 0x9f2d8e43;
    cont->seq = _seq++;
    cont->length = min(length, 1024 - sizeof(LogRecordContinuation));
    memcpy(block.data + sizeof(LogRecordContinuation), msg, cont->length);
    msg += cont->length;
    length -= cont->length;
    cont->continued = (length > 0);
    _pump.push(block);
  }
}

void RTSafePyLogSink::consume(Block block) {
  if (_msg.size() == 0) {
    LogRecordHeader* header = (LogRecordHeader*)block.data;
    assert(header->magic == 0x87b6c23a);
    _record.seq = header->seq;
    _record.level = header->level;
    strncpy(_record.logger, header->logger, MaxLoggerNameLength);
    _record.continued = header->continued;
    _msg = string(block.data + sizeof(LogRecordHeader), header->length);
  } else {
    LogRecordContinuation* cont = (LogRecordContinuation*)block.data;
    assert(cont->magic == 0x9f2d8e43);
    _record.seq = cont->seq;
    _record.continued = cont->continued;
    _msg += string(block.data + sizeof(LogRecordContinuation), cont->length);
  }

  if (!_record.continued) {
    _callback(_handle, _record.logger, _record.level, _msg.c_str());
    _msg = "";
  }
}

Logger::Logger(const char* name, LoggerRegistry* registry)
  : _registry(registry) {
  assert(strlen(name) < MaxLoggerNameLength - 1);
  strncpy(_name, name, MaxLoggerNameLength);
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
thread_local LogSink* LoggerRegistry::_local_sink = nullptr;

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

void LoggerRegistry::set_threadlocal_sink(LogSink* sink) {
  _local_sink = sink;
}

bool LoggerRegistry::cmp_cstr::operator()(const char *a, const char *b) {
  return strcmp(a, b) < 0;
}

}
