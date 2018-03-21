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

#ifndef _NOISICAA_AUDIOPROC_ENGINE_PUMP_H
#define _NOISICAA_AUDIOPROC_ENGINE_PUMP_H

#include <condition_variable>
#include <functional>
#include <memory>
#include <mutex>
#include <thread>
#include "noisicaa/core/fifo_queue.h"
#include "noisicaa/core/status.h"

namespace noisicaa {

using namespace std;

template<typename T>
class Pump {
public:
  Pump(Logger* logger, function<void(T)> callback);

  Status setup();
  void cleanup();

  void push(const T& item);

private:
  void thread_main();

  Logger* _logger;
  function<void(T)> _callback;

  unique_ptr<thread> _thread;
  bool _stop = false;
  mutex _cond_mutex;
  condition_variable _cond;
  FifoQueue<T, 128> _queue;
};

}  // namespace noisicaa

#endif
