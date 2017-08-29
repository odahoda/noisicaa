// -*- mode: c++ -*-

#ifndef _NOISICORE_STATUS_H
#define _NOISICORE_STATUS_H

#include <string>

namespace noisicaa {

using namespace std;

class Status {
public:
  enum Code {
    OK,
    ERROR,
  };

  Status()
    : _code(Code::ERROR),
      _message("Uninitialized status") {
  }

  Status(Code code, const string& message)
    : _code(code),
      _message(message) {
  }

  Status(const Status& s)
    : _code(s._code),
      _message(s._message) {
  }

  Code code() const { return _code; }
  bool is_error() const { return _code == Code::ERROR; }
  string message() const { return _message; }

  static Status Ok() { return Status(Code::OK, ""); }
  static Status Error(const string& message) { return Status(Code::ERROR, message); }

private:
  Code _code;
  string _message;
};

}  // namespace noisicaa

#endif
