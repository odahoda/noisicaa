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

#include <unistd.h>
#include "noisicaa/core/perf_stats.h"
#include "noisicaa/host_system/host_system.h"
#include "noisicaa/audioproc/engine/backend_null.h"
#include "noisicaa/audioproc/engine/block_context.h"
#include "noisicaa/audioproc/engine/realm.h"

namespace noisicaa {

NullBackend::NullBackend(
    HostSystem* host_system, const pb::BackendSettings& settings,
    void (*callback)(void*, const string&), void *userdata)
  : Backend(host_system, "noisicaa.audioproc.engine.backend.null", settings, callback, userdata) {}

NullBackend::~NullBackend() {}

Status NullBackend::setup(Realm* realm) {
  RETURN_IF_ERROR(Backend::setup(realm));
  return Status::Ok();
}

void NullBackend::cleanup() {
  Backend::cleanup();
}

Status NullBackend::begin_block(BlockContext* ctxt) {
  assert(ctxt->perf->current_span_id() == 0);
  ctxt->perf->start_span("frame");

  _block_start = std::chrono::high_resolution_clock::now();

  return Status::Ok();
}

Status NullBackend::end_block(BlockContext* ctxt) {
  ctxt->perf->end_span();
  assert(ctxt->perf->current_span_id() == 0);

  int64_t block_duration = (int64_t)(
      1e6 * (float)_host_system->block_size() / _host_system->sample_rate());
  int64_t elapsed = std::chrono::duration_cast<std::chrono::microseconds>(
      std::chrono::high_resolution_clock::now() - _block_start).count();
  int64_t delay = block_duration - elapsed;
  if (_settings.has_time_scale()) {
    delay = _settings.time_scale() * delay;
  }
  if (delay > 0) {
    usleep((useconds_t)delay);
  }

  return Status::Ok();
}

Status NullBackend::output(BlockContext* ctxt, Channel channel, BufferPtr buffer) {
  return Status::Ok();
}

}  // namespace noisicaa
