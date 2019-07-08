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

#include <assert.h>
#include <stdint.h>
#include <string.h>
#include "noisicaa/core/perf_stats.h"
#include "noisicaa/host_system/host_system.h"
#include "noisicaa/audioproc/engine/processor_csound.h"
#include "noisicaa/audioproc/engine/csound_util.h"
#include "noisicaa/audioproc/engine/rtcheck.h"

namespace noisicaa {

ProcessorCSoundBase::ProcessorCSoundBase(
    const string& realm_name, const string& node_id, const char* logger_name,
    HostSystem* host_system, const pb::NodeDescription& desc)
  : Processor(realm_name, node_id, logger_name, host_system, desc),
    _next_instance(nullptr),
    _current_instance(nullptr),
    _old_instance(nullptr) {}

ProcessorCSoundBase::~ProcessorCSoundBase() {}

Status ProcessorCSoundBase::set_code(const string& orchestra, const string& score) {
  // Discard any next instance, which hasn't been picked up by the audio thread.
  CSoundUtil* prev_next_instance = _next_instance.exchange(nullptr);
  if (prev_next_instance != nullptr) {
    delete prev_next_instance;
  }

  // Discard instance, which the audio thread doesn't use anymore.
  CSoundUtil* old_instance = _old_instance.exchange(nullptr);
  if (old_instance != nullptr) {
    delete old_instance;
  }

  // Create the next instance.
  unique_ptr<CSoundUtil> instance(
      new CSoundUtil(
          _host_system,
          bind(&ProcessorCSoundBase::handle_csound_log, this, placeholders::_1, placeholders::_2)));

  vector<CSoundUtil::PortSpec> ports;
  for (const auto& port : _desc.ports()) {
    assert(port.types_size() == 1);
    ports.emplace_back(
        CSoundUtil::PortSpec {
            port.name(),
            port.types(0),
            port.direction(),
            port.csound_name()
        });
  }

  RETURN_IF_ERROR(instance->setup(orchestra, score, ports));

  prev_next_instance = _next_instance.exchange(instance.release());
  assert(prev_next_instance == nullptr);

  return Status::Ok();
}

Status ProcessorCSoundBase::setup_internal() {
  return Processor::setup_internal();
}

void ProcessorCSoundBase::cleanup_internal() {
  CSoundUtil* instance = _next_instance.exchange(nullptr);
  if (instance != nullptr) {
    delete instance;
  }
  instance = _current_instance.exchange(nullptr);
  if (instance != nullptr) {
    delete instance;
  }
  instance = _old_instance.exchange(nullptr);
  if (instance != nullptr) {
    delete instance;
  }

  Processor::cleanup_internal();
}

Status ProcessorCSoundBase::process_block_internal(BlockContext* ctxt, TimeMapper* time_mapper) {
  PerfTracker tracker(ctxt->perf.get(), "csound");

  // If there is a next instance, make it the current. The current instance becomes
  // the old instance, which will eventually be destroyed in the main thread.
  // It must not happen that a next instance is available, before an old one has
  // been disposed of.
  CSoundUtil* instance = _next_instance.exchange(nullptr);
  if (instance != nullptr) {
    CSoundUtil* old_instance = _current_instance.exchange(instance);
    old_instance = _old_instance.exchange(old_instance);
    assert(old_instance == nullptr);
  }

  instance = _current_instance.load();
  if (instance == nullptr) {
    // No instance yet, just clear my output ports.
    clear_all_outputs();
    return Status::Ok();
  }

  return instance->process_block(ctxt, time_mapper, _buffers);
}

void ProcessorCSoundBase::handle_csound_log(LogLevel level, const char* msg) {
  _logger->log(level, "%s", msg);
}

}
