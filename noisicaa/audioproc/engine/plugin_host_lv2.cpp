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

#include "noisicaa/core/logging.h"
#include "noisicaa/core/perf_stats.h"
#include "noisicaa/lv2/feature_manager.h"
#include "noisicaa/host_system/host_system.h"
#include "noisicaa/audioproc/engine/plugin_ui_host_lv2.h"
#include "noisicaa/audioproc/engine/plugin_host_lv2.h"

namespace noisicaa {

PluginHostLV2::PluginHostLV2(const pb::PluginInstanceSpec& spec, HostSystem* host_system)
  : PluginHost(spec, host_system, "noisicaa.audioproc.plugins.lv2") {
}

PluginHostLV2::~PluginHostLV2() {}

StatusOr<PluginUIHost*> PluginHostLV2::create_ui(
    void* handle,
    void (*control_value_change_cb)(void*, uint32_t, float)) {
  return new PluginUIHostLV2(this, _host_system, handle, control_value_change_cb);
}

Status PluginHostLV2::setup() {
  RETURN_IF_ERROR(PluginHost::setup());

  assert(_spec.node_description().has_plugin());
  assert(_spec.node_description().plugin().type() == pb::PluginDescription::LV2);
  assert(_spec.node_description().has_lv2());
  const pb::LV2Description& lv2_desc = _spec.node_description().lv2();

  LilvWorld *world = _host_system->lv2->lilv_world;
  assert(world != nullptr);

  _logger->info("Loading LV2 plugin %s...", lv2_desc.uri().c_str());
  const LilvPlugins* all_plugins = lilv_world_get_all_plugins(world);
  LilvNode* uri_node = lilv_new_uri(world, lv2_desc.uri().c_str());
  _plugin = lilv_plugins_get_by_uri(all_plugins, uri_node);
  lilv_free(uri_node);
  if (_plugin == nullptr) {
    return ERROR_STATUS("Plugin '%s' not found.", lv2_desc.uri().c_str());
  }

  _feature_manager.reset(new LV2PluginFeatureManager(_host_system));

  _logger->info("Creating LV2 instance for %s...", lv2_desc.uri().c_str());
  _instance = lilv_plugin_instantiate(
      _plugin,
      _host_system->sample_rate(),
      _feature_manager->get_features());
  if (_instance == nullptr) {
    return ERROR_STATUS("Failed to instantiate '%s'.", lv2_desc.uri().c_str());
  }

  lilv_instance_activate(_instance);

  return Status::Ok();
}

void PluginHostLV2::cleanup() {
  if (_instance != nullptr) {
    lilv_instance_deactivate(_instance);
    lilv_instance_free(_instance);
    _instance = nullptr;
  }

  if (_plugin != nullptr) {
    _plugin = nullptr;
  }

  _feature_manager.reset();

  PluginHost::cleanup();
}

Status PluginHostLV2::connect_port(uint32_t port_idx, BufferPtr buf) {
  lilv_instance_connect_port(_instance, port_idx, buf);
  return Status::Ok();
}

Status PluginHostLV2::process_block(uint32_t block_size) {
  //PerfTracker tracker(ctxt->perf.get(), "lv2");
  lilv_instance_run(_instance, block_size);
  return Status::Ok();
}

}
