#ifndef _NOISICORE_MISC_H
#define _NOISICORE_MISC_H

#include <string>

namespace noisicaa {

std::string sprintf(const std::string& fmt, ...);

enum LogLevel {
  INFO, WARNING, ERROR
};

void log(LogLevel log_level, const char* fmt, ...);

struct ScopeGuardBase {
  ScopeGuardBase() : _active(true) {}

  ScopeGuardBase(ScopeGuardBase&& rhs) : _active(rhs._active) {
    rhs.dismiss();
  }

  void dismiss() { _active = false; }

 protected:
  ~ScopeGuardBase() = default;
  bool _active;
};

template<class F> struct ScopeGuard: public ScopeGuardBase {
  ScopeGuard() = delete;
  ScopeGuard(const ScopeGuard&) = delete;

  ScopeGuard(F f)
    : ScopeGuardBase(),
      _f(std::move(f)) {}

  ScopeGuard(ScopeGuard&& rhs)
    : ScopeGuardBase(std::move(rhs)),
      _f(std::move(rhs._f)) {}

  ~ScopeGuard() {
    if (_active) {
      _f();
    }
  }

  ScopeGuard& operator=(const ScopeGuard&) = delete;

 private:
  F _f;
};

template<class F> ScopeGuard<F> scopeGuard(F f) {
  return ScopeGuard<F>(std::move(f));
}

}  // namespace noisicaa

#endif
