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

#include <memory>
#include <string>
#include <assert.h>
#include <stdint.h>
#include "noisicaa/core/perf_stats.h"
#include "noisicaa/audioproc/vm/host_data.h"
#include "noisicaa/audioproc/vm/processor_lv2.h"

namespace noisicaa {

ProcessorLV2::ProcessorLV2(const string& node_id, HostData* host_data)
  : Processor(node_id, "noisicaa.audioproc.vm.processor.lv2", host_data) {}

ProcessorLV2::~ProcessorLV2() {}

Status ProcessorLV2::setup(const ProcessorSpec* spec) {
  Status status = Processor::setup(spec);
  RETURN_IF_ERROR(status);

  StatusOr<string> stor_uri = get_string_parameter("lv2_uri");
  RETURN_IF_ERROR(stor_uri);
  string uri = stor_uri.result();

  LilvWorld *world = _host_data->lv2->lilv_world;
  assert(world != nullptr);

  const LilvPlugins* all_plugins = lilv_world_get_all_plugins(world);

  LilvNode* uri_node = lilv_new_uri(world, uri.c_str());
  _plugin = lilv_plugins_get_by_uri(all_plugins, uri_node);
  lilv_free(uri_node);
  if (_plugin == nullptr) {
    return ERROR_STATUS("Plugin '%s' not found.", uri.c_str());
  }

  LilvNodes* supported_features = lilv_plugin_get_supported_features(_plugin);
  if (supported_features == nullptr) {
    return ERROR_STATUS("Failed to get supported features.");
  }

  vector<string> feature_uris;
  LilvIter* it = lilv_nodes_begin(supported_features);
  while (!lilv_nodes_is_end(supported_features, it)) {
    const LilvNode* node = lilv_nodes_get(supported_features, it);
    assert(lilv_node_is_uri(node));
    const char* uri = lilv_node_as_uri(node);
    if (_host_data->lv2->supports_feature(uri)) {
      _logger->info("with feature %s", uri);
      feature_uris.emplace_back(uri);
    }
    it = lilv_nodes_next(supported_features, it);
  }
  lilv_nodes_free(supported_features);

  _features = new LV2_Feature*[feature_uris.size() + 1];

  LV2_Feature** feature = _features;
  for (const string& uri : feature_uris) {
    *feature++ = _host_data->lv2->create_feature(uri);
  }
  *feature = nullptr;

  _instance = lilv_plugin_instantiate(_plugin, 44100.0, _features);
  if (_instance == nullptr) {
    return ERROR_STATUS("Failed to instantiate '%s'.", uri.c_str());
  }

  lilv_instance_activate(_instance);

  return Status::Ok();
}

void ProcessorLV2::cleanup() {
  if (_instance != nullptr) {
    lilv_instance_deactivate(_instance);
    lilv_instance_free(_instance);
    _instance = nullptr;
  }

  if (_features) {
    for (LV2_Feature** it = _features ; *it ; ++it) {
      _host_data->lv2->delete_feature(*it);
    }
    delete _features;
    _features = nullptr;
  }

  if (_plugin != nullptr) {
    _plugin = nullptr;
  }
  Processor::cleanup();
}

Status ProcessorLV2::connect_port(uint32_t port_idx, BufferPtr buf) {
  lilv_instance_connect_port(_instance, port_idx, buf);
  return Status::Ok();
}

Status ProcessorLV2::run(BlockContext* ctxt, TimeMapper* time_mapper) {
  PerfTracker tracker(ctxt->perf.get(), "lv2");
  lilv_instance_run(_instance, ctxt->block_size);
  return Status::Ok();
}

}
