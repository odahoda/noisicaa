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

#include <unistd.h>
#include "noisicaa/core/perf_stats.h"
#include "noisicaa/audioproc/vm/backend_null.h"
#include "noisicaa/audioproc/vm/block_context.h"
#include "noisicaa/audioproc/vm/vm.h"

namespace noisicaa {

NullBackend::NullBackend(const BackendSettings& settings)
  : Backend("noisicaa.audioproc.vm.backend.null", settings),
    _new_block_size(settings.block_size) {}
NullBackend::~NullBackend() {}

Status NullBackend::setup(VM* vm) {
  Status status = Backend::setup(vm);
  RETURN_IF_ERROR(status);

  if (_settings.block_size == 0) {
   return ERROR_STATUS("Invalid block_size %d", _settings.block_size);
  }

  vm->set_block_size(_settings.block_size);
  return Status::Ok();
}

void NullBackend::cleanup() {
  Backend::cleanup();
}

Status NullBackend::set_block_size(uint32_t block_size) {
  if (block_size == 0) {
   return ERROR_STATUS("Invalid block_size %d", block_size);
  }

  _new_block_size = block_size;
  return Status::Ok();
}

Status NullBackend::begin_block(BlockContext* ctxt) {
  assert(ctxt->perf->current_span_id() == 0);
  ctxt->perf->start_span("frame");

  if (_new_block_size != _settings.block_size) {
    _settings.block_size = _new_block_size;
    _vm->set_block_size(_settings.block_size);
  }

  _block_start = std::chrono::high_resolution_clock::now();

  return Status::Ok();
}

Status NullBackend::end_block(BlockContext* ctxt) {
  ctxt->perf->end_span();
  assert(ctxt->perf->current_span_id() == 0);

  int64_t block_duration = (int64_t)(1e6 * (float)ctxt->block_size / 44100.0);
  int64_t elapsed = std::chrono::duration_cast<std::chrono::microseconds>(
      std::chrono::high_resolution_clock::now() - _block_start).count();
  int64_t delay = block_duration - elapsed;
  if (delay > 0) {
    usleep((useconds_t)(_settings.time_scale * delay));
  }

  return Status::Ok();
}

Status NullBackend::output(BlockContext* ctxt, const string& channel, BufferPtr samples) {
  return Status::Ok();
}

}  // namespace noisicaa
