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

#include <random>

#include "noisicaa/core/slots.h"

namespace noisicaa {

using namespace std;

template<typename... ARGS>
typename Slot<ARGS...>::Listener Slot<ARGS...>::connect(Callback callback) {
  static mt19937_64 rand(time(0));
  Listener listener = rand();
  _connections.emplace_back(Connection{ listener, callback });
  return listener;
}

template<typename... ARGS>
void Slot<ARGS...>::disconnect(Listener listener) {
  auto it = _connections.begin();
  while (it != _connections.end()) {
    if (it->listener == listener) {
      it = _connections.erase(it);
    } else {
      ++it;
    }
  }
}

template<typename... ARGS>
void Slot<ARGS...>::emit(ARGS... args) {
  for (const auto& it : _connections) {
    it.callback(args...);
  }
}

}  // namespace noisicaa
