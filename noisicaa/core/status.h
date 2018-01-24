// -*- mode: c++ -*-

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

#ifndef _NOISICAA_CORE_STATUS_H
#define _NOISICAA_CORE_STATUS_H

#include <string>
#include <assert.h>

namespace noisicaa {

using namespace std;

class Status {
public:
  enum Code {
    OK,
    ERROR,
    CONNECTION_CLOSED,
    OS_ERROR,
  };

  Status()
    : _code(Code::ERROR),
      _file("<undefined>"),
      _line(-1),
      _message("Uninitialized status") {
  }

  Status(Code code, const char* file, int line, const string& message)
    : _code(code),
      _file(file),
      _line(line),
      _message(message) {
  }

  Status(const Status& s)
    : _code(s._code),
      _file(s._file),
      _line(s._line),
      _message(s._message) {
  }

  Code code() const { return _code; }
  const char* file() const { return _file; }
  int line() const { return _line; }
  bool is_error() const { return _code != Code::OK; }
  bool is_connection_closed() const { return _code == Code::CONNECTION_CLOSED; }
  bool is_os_error() const { return _code == Code::OS_ERROR; }
  string message() const { return _message; }

  static Status Ok() { return Status(Code::OK, nullptr, 0, ""); }
  static Status Error(const char* file, int line, const string& message) {
    return Status(Code::ERROR, file, line, message);
  }
  static Status Error(const char* file, int line, const char* fmt, ...);
  static Status ConnectionClosed(const char* file, int line) {
    return Status(Code::CONNECTION_CLOSED, file, line, "Connection closed");
  }
  static Status OSError(const char* file, int line, const string& message);
  static Status OSError(const char* file, int line, const char* fmt, ...);

private:
  Code _code;
  const char* _file;
  int _line;
  string _message;
};

#define ERROR_STATUS(...) Status::Error(__FILE__, __LINE__, __VA_ARGS__)
#define CONNECTION_CLOSED_STATUS() Status::ConnectionClosed(__FILE__, __LINE__)
#define OSERROR_STATUS(...) Status::OSError(__FILE__, __LINE__, __VA_ARGS__)

#define RETURN_IF_ERROR(STATUS) do { if (STATUS.is_error()) { return STATUS; } } while (false)

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

}  // namespace noisicaa

#endif
