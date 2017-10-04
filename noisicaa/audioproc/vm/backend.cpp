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

#include "capnp/serialize.h"
#include "noisicaa/core/message.capnp.h"
#include "noisicaa/audioproc/vm/backend.h"
#include "noisicaa/audioproc/vm/backend_ipc.h"
#include "noisicaa/audioproc/vm/backend_null.h"
#include "noisicaa/audioproc/vm/backend_portaudio.h"

namespace noisicaa {

Backend::Backend(const char* logger_name, const BackendSettings& settings)
  : _logger(LoggerRegistry::get_logger(logger_name)),
    _settings(settings) {}

Backend::~Backend() {
  cleanup();
}

StatusOr<Backend*> Backend::create(const string& name, const BackendSettings& settings) {
  if (name == "portaudio") {
    return new PortAudioBackend(settings);
  } else if (name == "ipc") {
    return new IPCBackend(settings);
  } else if (name == "null") {
    return new NullBackend(settings);
  }

  return ERROR_STATUS("Invalid backend name '%s'", name.c_str());
}

Status Backend::setup(VM* vm) {
  _vm = vm;
  _stopped = false;
  return Status::Ok();
}

void Backend::cleanup() {
}

Status Backend::send_message(const string& msg_bytes) {
  lock_guard<mutex> lock(_msg_queue_mutex);
  _msg_queue.emplace_back(msg_bytes);
  return Status::Ok();
}

Status Backend::set_block_size(uint32_t block_size) {
  return ERROR_STATUS("Block size changes not supported.");
}

}  // namespace noisicaa
