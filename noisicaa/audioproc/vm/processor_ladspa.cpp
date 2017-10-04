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

#include <dlfcn.h>
#include <stdint.h>
#include "noisicaa/core/perf_stats.h"
#include "noisicaa/audioproc/vm/processor_ladspa.h"

namespace noisicaa {

ProcessorLadspa::ProcessorLadspa(const string& node_id, HostData* host_data)
  : Processor(node_id, "noisicaa.audioproc.vm.processor.ladspa", host_data) {}

ProcessorLadspa::~ProcessorLadspa() {}

Status ProcessorLadspa::setup(const ProcessorSpec* spec) {
  Status status = Processor::setup(spec);
  if (status.is_error()) { return status; }

  StatusOr<string> stor_or_library_path = get_string_parameter("ladspa_library_path");
  if (stor_or_library_path.is_error()) { return stor_or_library_path; }
  string library_path = stor_or_library_path.result();

  StatusOr<string> stor_or_label = get_string_parameter("ladspa_plugin_label");
  if (stor_or_label.is_error()) { return stor_or_label; }
  string label = stor_or_label.result();

  _library = dlopen(library_path.c_str(), RTLD_NOW);
  if (_library == nullptr) {
    return Status::Error("Failed to open LADSPA plugin: %s", dlerror());
  }

  LADSPA_Descriptor_Function lib_descriptor =
    (LADSPA_Descriptor_Function)dlsym(_library, "ladspa_descriptor");

  char* error = dlerror();
  if (error != nullptr) {
    return Status::Error("Failed to open LADSPA plugin: %s", error);
  }

  int idx = 0;
  while (true) {
    const LADSPA_Descriptor* desc = lib_descriptor(idx);
    if (desc == nullptr) { break; }

    if (!strcmp(desc->Label, label.c_str())) {
      _descriptor = desc;
      break;
    }

    ++idx;
  }

  if (_descriptor == nullptr) {
    return Status::Error("No LADSPA plugin with label %s found.", label.c_str());
  }

  _instance = _descriptor->instantiate(_descriptor, 44100);
  if (_instance == nullptr) {
    return Status::Error("Failed to instantiate LADSPA plugin.");
  }

  if (_descriptor->activate != nullptr) {
    _descriptor->activate(_instance);
  }

  return Status::Ok();
}

void ProcessorLadspa::cleanup() {
  if (_instance != nullptr) {
    assert(_descriptor != nullptr);
    if (_descriptor->deactivate != nullptr) {
      _descriptor->deactivate(_instance);
    }
    _descriptor->cleanup(_instance);
    _instance = nullptr;
  }

  if (_descriptor != nullptr) {
    _descriptor = nullptr;
  }

  if (_library != nullptr) {
    dlclose(_library);
    _library = nullptr;
  }

  Processor::cleanup();
}

Status ProcessorLadspa::connect_port(uint32_t port_idx, BufferPtr buf) {
  assert(port_idx < _descriptor->PortCount);
  _descriptor->connect_port(_instance, port_idx, (LADSPA_Data*)buf);
  return Status::Ok();
}

Status ProcessorLadspa::run(BlockContext* ctxt) {
  PerfTracker tracker(ctxt->perf.get(), "ladspa");

  _descriptor->run(_instance, ctxt->block_size);
  return Status::Ok();
}

}
