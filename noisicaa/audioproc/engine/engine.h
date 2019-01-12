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

#ifndef _NOISICAA_AUDIOPROC_ENGINE_ENGINE_H
#define _NOISICAA_AUDIOPROC_ENGINE_ENGINE_H

#include <atomic>
#include <chrono>
#include <condition_variable>
#include <mutex>
#include <thread>

#include "noisicaa/core/logging.h"
#include "noisicaa/core/status.h"
#include "noisicaa/host_system/host_system.h"
#include "noisicaa/audioproc/engine/backend.h"
#include "noisicaa/audioproc/engine/message_queue.h"
#include "noisicaa/audioproc/engine/realm.h"

namespace noisicaa {

using namespace std;

class Engine {
public:
  Engine(HostSystem* host_system, void (*callback)(void*, const string&), void* userdata);
  virtual ~Engine();

  Status setup();
  void cleanup();

  Status setup_thread();
  void exit_loop();
  Status loop(Realm* realm, Backend* backend);

private:
  HostSystem* _host_system;
  Logger* _logger;
  void (*_callback)(void*, const string&);
  void *_userdata;

  bool _exit_loop;

  unique_ptr<thread> _out_messages_pump;
  bool _stop = false;
  mutex _cond_mutex;
  condition_variable _cond;
  void out_messages_pump_main();

  atomic<MessageQueue*> _next_out_messages;
  atomic<MessageQueue*> _current_out_messages;
  atomic<MessageQueue*> _old_out_messages;

};

}  // namespace noisicaa

#endif
