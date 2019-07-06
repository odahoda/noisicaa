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

#include <math.h>

#include "noisicaa/audioproc/engine/misc.h"
#include "noisicaa/audioproc/public/engine_notification.pb.h"
#include "noisicaa/audioproc/public/transfer_function.h"
#include "noisicaa/audioproc/engine/message_queue.h"
#include "noisicaa/host_system/host_system.h"
#include "noisicaa/builtin_nodes/cv_mapper/processor.h"
#include "noisicaa/builtin_nodes/cv_mapper/processor.pb.h"

namespace noisicaa {

ProcessorCVMapper::ProcessorCVMapper(
    const string& realm_name, const string& node_id, HostSystem *host_system,
    const pb::NodeDescription& desc)
  : Processor(
      realm_name, node_id, "noisicaa.audioproc.engine.processor.cv_mapper", host_system, desc),
    _next_spec(nullptr),
    _current_spec(nullptr),
    _old_spec(nullptr) {
}

Status ProcessorCVMapper::setup_internal() {
  return Processor::setup_internal();
}

void ProcessorCVMapper::cleanup_internal() {
  pb::CVMapperSpec* spec = _next_spec.exchange(nullptr);
  if (spec != nullptr) {
    delete spec;
  }
  spec = _current_spec.exchange(nullptr);
  if (spec != nullptr) {
    delete spec;
  }
  spec = _old_spec.exchange(nullptr);
  if (spec != nullptr) {
    delete spec;
  }

  Processor::cleanup_internal();
}

Status ProcessorCVMapper::set_parameters_internal(const pb::NodeParameters& parameters) {
  if (parameters.HasExtension(pb::cv_mapper_spec)) {
    const auto& spec = parameters.GetExtension(pb::cv_mapper_spec);

    Status status = set_spec(spec);
    if (status.is_error()) {
      _logger->warning("Failed to update spec: %s", status.message());
    }
  }

  return Processor::set_parameters_internal(parameters);
}

Status ProcessorCVMapper::process_block_internal(BlockContext* ctxt, TimeMapper* time_mapper) {
  // If there is a next spec, make it the current. The current spec becomes the old spec, which will
  // eventually be destroyed in the main thread.  It must not happen that a next spec is available,
  // before an old one has been disposed of.
  pb::CVMapperSpec* spec = _next_spec.exchange(nullptr);
  if (spec != nullptr) {
    pb::CVMapperSpec* old_spec = _current_spec.exchange(spec);
    old_spec = _old_spec.exchange(old_spec);
    assert(old_spec == nullptr);
  }

  spec = _current_spec.load();
  if (spec == nullptr) {
    // No spec yet, just clear my output ports.
    clear_all_outputs();
    return Status::Ok();
  }

  float* in = (float*)_buffers[0];
  float* out = (float*)_buffers[1];

  for (uint32_t pos = 0; pos < _host_system->block_size(); ++pos) {
    *out = apply_transfer_function(spec->transfer_function(), *in);
    ++in;
    ++out;
  }

  return Status::Ok();
}

Status ProcessorCVMapper::set_spec(const pb::CVMapperSpec& spec) {
  _logger->info("Setting spec:\n%s", spec.DebugString().c_str());

  // Discard any next spec, which hasn't been picked up by the audio thread.
  pb::CVMapperSpec* prev_next_spec = _next_spec.exchange(nullptr);
  if (prev_next_spec != nullptr) {
    delete prev_next_spec;
  }

  // Discard spec, which the audio thread doesn't use anymore.
  pb::CVMapperSpec* old_spec = _old_spec.exchange(nullptr);
  if (old_spec != nullptr) {
    delete old_spec;
  }

  // Create the new spec.
  unique_ptr<pb::CVMapperSpec> new_spec(new pb::CVMapperSpec());
  new_spec->CopyFrom(spec);

  // Make the new spec the next one for the audio thread.
  prev_next_spec = _next_spec.exchange(new_spec.release());
  assert(prev_next_spec == nullptr);

  return Status::Ok();
}

}
