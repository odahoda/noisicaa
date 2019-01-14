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

#ifndef _NOISICAA_CORE_STATUS_H
#define _NOISICAA_CORE_STATUS_H

#include <assert.h>
#include <stddef.h>
#include <condition_variable>
#include <mutex>

namespace noisicaa {

using namespace std;

class Status {
public:
  enum Code {
    OK,
    ERROR,
    CONNECTION_CLOSED,
    OS_ERROR,
    TIMEOUT,
  };

  static const size_t MaxMessageLength = 1024;

  Status()
    : _code(Code::ERROR),
      _file("<undefined>"),
      _line(-1),
      _message(-2) {
  }

  Status(Code code, const char* file, int line, const char* message)
    : _code(code),
      _file(file),
      _line(line),
      _message(allocate_message(message)) {
  }

  Status(const Status& s)
    : _code(s._code),
      _file(s._file),
      _line(s._line),
      _message(allocate_message(s.message())) {
  }

  ~Status() {
    if (_message >= 0) {
      _messages[_message][0] = 0;
    }
  }

  Code code() const { return _code; }
  const char* file() const { return _file; }
  int line() const { return _line; }
  bool is_error() const { return _code != Code::OK; }
  bool is_connection_closed() const { return _code == Code::CONNECTION_CLOSED; }
  bool is_timeout() const { return _code == Code::TIMEOUT; }
  bool is_os_error() const { return _code == Code::OS_ERROR; }
  const char* message() const;

  static Status Ok() { return Status(Code::OK, nullptr, 0, ""); }
  static Status Error(const char* file, int line, const char* fmt, ...);
  static Status ConnectionClosed(const char* file, int line) {
    return Status(Code::CONNECTION_CLOSED, file, line, "Connection closed");
  }
  static Status Timeout(const char* file, int line) {
    return Status(Code::TIMEOUT, file, line, "Timeout");
  }
  static Status OSError(const char* file, int line, const char* fmt, ...);

private:
  Code _code;
  const char* _file;
  int _line;

  int _message;
  static const int NumMessageSlots = 10;
  static thread_local char _messages[NumMessageSlots][MaxMessageLength];
  static int allocate_message(const char* msg);
};

#define ERROR_STATUS(...) Status::Error(__FILE__, __LINE__, __VA_ARGS__)
#define CONNECTION_CLOSED_STATUS() Status::ConnectionClosed(__FILE__, __LINE__)
#define TIMEOUT_STATUS() Status::Timeout(__FILE__, __LINE__)
#define OSERROR_STATUS(...) Status::OSError(__FILE__, __LINE__, __VA_ARGS__)

#define RETURN_IF_ERROR(STATUS) do { Status __s = STATUS; if (__s.is_error()) { return __s; } } while (false)
#define RETURN_IF_PTHREAD_ERROR(STATUS) do { int __s = STATUS; if (__s == ETIMEDOUT) { return TIMEOUT_STATUS(); } else if (__s != 0) { return OSERROR_STATUS("pthread function failed"); } } while (false)
#define RETURN_IF_ALSA_ERROR(STATUS) do { int __s = STATUS; if (__s < 0) { return ERROR_STATUS("ALSA error %d: %s", __s, snd_strerror(__s)); } } while (false)

template<class T> class StatusOr : public Status {
public:
  StatusOr()
    : Status(),
      _result() {}

  StatusOr(const StatusOr& s)
    : Status(s),
      _result(s._result) {}

  StatusOr(const Status& s)
    : Status(s),
      _result() {}

  StatusOr(T result)
    : Status(Code::OK, nullptr, 0, ""),
      _result(result) {}

  T result() const { assert(!is_error()); return _result; }

private:
  T _result;
};

class StatusSignal {
public:
  StatusSignal() {}

  Status wait() {
    unique_lock<mutex> lock(_cond_mutex);
    _cond.wait(lock);
    return _status;
  }

  void set(Status status) {
    lock_guard<mutex> lock(_cond_mutex);
    _status = status;
    _cond.notify_all();
  }

private:
  Status _status;
  condition_variable _cond;
  mutex _cond_mutex;
};

}  // namespace noisicaa

#endif
