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

#include "noisicaa/audioproc/engine/pump.h"

namespace noisicaa {

template<typename T>
Pump<T>::Pump(Logger* logger, function<void(T)> callback)
  : _logger(logger),
    _callback(callback) {}

template<typename T>
Status Pump<T>::setup() {
  if (_callback) {
    _stop = false;
    _thread.reset(new thread(&Pump<T>::thread_main, this));
  }

  return Status::Ok();
}

template<typename T>
void Pump<T>::cleanup() {
  if (_thread.get() != nullptr) {
    {
      lock_guard<mutex> lock(_cond_mutex);
      _stop = true;
      _cond.notify_all();
    }

    _thread->join();
    _thread.reset();
  }
}

template<typename T>
void Pump<T>::thread_main() {
  _logger->info("Pump thread started.");
  unique_lock<mutex> lock(_cond_mutex);
  while (true) {
    _cond.wait_for(lock, chrono::milliseconds(500));

    T item;
    while (_queue.pop(item)) {
      _callback(item);
    }

    if (_stop) {
      break;
    }
  }
  _logger->info("Pump thread stopped.");
}

template<typename T>
void Pump<T>::push(const T& item) {
  if (_thread.get() != nullptr) {
    _queue.push(item);
    _cond.notify_all();
  }
}

}  // namespace noisicaa
