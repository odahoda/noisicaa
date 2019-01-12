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

#include <dlfcn.h>
#include "noisicaa/core/logging.h"
#include "noisicaa/core/perf_stats.h"
#include "noisicaa/host_system/host_system.h"
#include "noisicaa/audioproc/engine/plugin_host_ladspa.h"

namespace noisicaa {

PluginHostLadspa::PluginHostLadspa(const pb::PluginInstanceSpec& spec, HostSystem* host_system)
  : PluginHost(spec, host_system, "noisicaa.audioproc.plugins.ladspa") {
}

PluginHostLadspa::~PluginHostLadspa() {}

Status PluginHostLadspa::setup() {
  RETURN_IF_ERROR(PluginHost::setup());

  assert(_spec.node_description().has_plugin());
  assert(_spec.node_description().plugin().type() == pb::PluginDescription::LADSPA);
  assert(_spec.node_description().has_ladspa());
  const pb::LadspaDescription& ladspa_desc = _spec.node_description().ladspa();

  _library = dlopen(ladspa_desc.library_path().c_str(), RTLD_NOW);
  if (_library == nullptr) {
    return ERROR_STATUS("Failed to open LADSPA plugin: %s", dlerror());
  }

  LADSPA_Descriptor_Function lib_descriptor =
    (LADSPA_Descriptor_Function)dlsym(_library, "ladspa_descriptor");

  char* error = dlerror();
  if (error != nullptr) {
    return ERROR_STATUS("Failed to open LADSPA plugin: %s", error);
  }

  int idx = 0;
  while (true) {
    const LADSPA_Descriptor* desc = lib_descriptor(idx);
    if (desc == nullptr) { break; }

    if (!strcmp(desc->Label, ladspa_desc.label().c_str())) {
      _descriptor = desc;
      break;
    }

    ++idx;
  }

  if (_descriptor == nullptr) {
    return ERROR_STATUS("No LADSPA plugin with label %s found.", ladspa_desc.label().c_str());
  }

  _instance = _descriptor->instantiate(_descriptor, _host_system->sample_rate());
  if (_instance == nullptr) {
    return ERROR_STATUS("Failed to instantiate LADSPA plugin.");
  }

  if (_descriptor->activate != nullptr) {
    _descriptor->activate(_instance);
  }

  return Status::Ok();
}

void PluginHostLadspa::cleanup() {
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

  PluginHost::cleanup();
}

Status PluginHostLadspa::connect_port(uint32_t port_idx, BufferPtr buf) {
  assert(port_idx < _descriptor->PortCount);
  _descriptor->connect_port(_instance, port_idx, (LADSPA_Data*)buf);
  return Status::Ok();
}

Status PluginHostLadspa::process_block(uint32_t block_size) {
  //PerfTracker tracker(ctxt->perf.get(), "ladspa");
  _descriptor->run(_instance, block_size);
  return Status::Ok();
}

}
