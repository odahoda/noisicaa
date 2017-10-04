// -*- mode: c++ -*-

/*
 * @begin:license
 *
 * Copyright (c) 2015-2017, Benjamin Niemann <pink@odahoda.de>
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

#ifndef _NOISICAA_AUDIOPROC_VM_BACKEND_H
#define _NOISICAA_AUDIOPROC_VM_BACKEND_H

#include <mutex>
#include <string>
#include <vector>
#include "noisicaa/core/logging.h"
#include "noisicaa/core/status.h"
#include "noisicaa/audioproc/vm/buffers.h"

namespace noisicaa {

using namespace std;

class BlockContext;
class VM;

struct BackendSettings {
  string ipc_address;
  uint32_t block_size;
  float time_scale;
};

class Backend {
public:
  virtual ~Backend();

  static StatusOr<Backend*> create(const string& name, const BackendSettings& settings);

  virtual Status setup(VM* vm);
  virtual void cleanup();

  Status send_message(const string& msg);
  virtual Status set_block_size(uint32_t block_size);

  virtual Status begin_block(BlockContext* ctxt) = 0;
  virtual Status end_block(BlockContext* ctxt) = 0;
  virtual Status output(BlockContext* ctxt, const string& channel, BufferPtr samples) = 0;

  void stop() { _stopped = true; }
  bool stopped() const { return _stopped; }

  void release() { _released = true; }
  bool released() const { return _released; }

protected:
  Backend(const char* logger_name, const BackendSettings& settings);

  Logger* _logger;
  BackendSettings _settings;
  VM* _vm = nullptr;
  bool _stopped = false;
  bool _released = false;

  mutex _msg_queue_mutex;
  vector<string> _msg_queue;
};

}  // namespace noisicaa

#endif
