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

#ifndef _NOISICAA_CORE_SCOPE_GUARD_H
#define _NOISICAA_CORE_SCOPE_GUARD_H

#include <string>

namespace noisicaa {

using namespace std;

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
      _f(move(f)) {}

  ScopeGuard(ScopeGuard&& rhs)
    : ScopeGuardBase(move(rhs)),
      _f(move(rhs._f)) {}

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
  return ScopeGuard<F>(move(f));
}

}  // namespace noisicaa

#endif
