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
#include "noisicaa/core/slots.inl.h"
#include "noisicaa/lv2/feature_manager.h"
#include "noisicaa/host_system/host_system.h"
#include "noisicaa/audioproc/public/plugin_state.pb.h"
#include "noisicaa/audioproc/engine/pump.inl.h"
#include "noisicaa/audioproc/engine/plugin_ui_host_lv2.h"
#include "noisicaa/audioproc/engine/plugin_host_lv2.h"

namespace noisicaa {

PluginHostLV2::PluginHostLV2(const pb::PluginInstanceSpec& spec, HostSystem* host_system)
  : PluginHost(spec, host_system, "noisicaa.audioproc.plugins.lv2"),
    _control_value_pump(
        _logger, bind(&PluginHostLV2::control_value_change, this, placeholders::_1)) {
}

PluginHostLV2::~PluginHostLV2() {}

StatusOr<PluginUIHost*> PluginHostLV2::create_ui(
    void* handle,
    void (*control_value_change_cb)(void*, uint32_t, float, uint32_t)) {
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

  _state_interface = (LV2_State_Interface*)lilv_instance_get_extension_data(
      _instance, LV2_STATE__interface);
  if (_state_interface != nullptr) {
    _logger->info("Plugin supports interface %s", LV2_STATE__interface);
  } else {
    _logger->info("Plugin does not support interface %s", LV2_STATE__interface);
  }

  lilv_instance_activate(_instance);

  if (_state_interface != nullptr && _spec.has_initial_state()) {
    RETURN_IF_ERROR(set_state(_spec.initial_state()));
  }

  _portmap.resize(_spec.node_description().ports_size());
  for (int idx = 0 ; idx < _spec.node_description().ports_size() ; ++idx ) {
    const auto& port = _spec.node_description().ports(idx);

    if (port.direction() == pb::PortDescription::INPUT
        and port.type() == pb::PortDescription::KRATE_CONTROL) {
      _rt_control_values[idx] = ControlValue{0.0, 0};
      _control_values[idx] = ControlValue{0.0, 1};
    }

    _portmap[idx] = nullptr;
  }

  RETURN_IF_ERROR(_control_value_pump.setup());

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

  _portmap.clear();

  _control_value_pump.cleanup();
  _rt_control_values.clear();
  _control_values.clear();

  PluginHost::cleanup();
}

Slot<int, float, uint32_t>::Listener PluginHostLV2::subscribe_to_control_value_changes(
    function<void(int, float, uint32_t)> callback) {
  lock_guard<mutex> guard(_control_values_mutex);

  for (const auto& it : _control_values) {
    callback(it.first, it.second.value, it.second.generation);
  }

  return _control_value_changed.connect(callback);
}

void PluginHostLV2::unsubscribe_from_control_value_changes(
    Slot<int, float, uint32_t>::Listener listener) {
  _control_value_changed.disconnect(listener);
}

void PluginHostLV2::control_value_change(const ControlValueChange& change) {
  {
    lock_guard<mutex> guard(_control_values_mutex);
    const auto& it = _control_values.find(change.port_idx);
    assert(it != _control_values.end());
    it->second.value = change.value;
    it->second.generation = change.generation;
  }

  _logger->info(
      "control_value_change(%d, %f, %d)", change.port_idx, change.value, change.generation);
  _control_value_changed.emit(change.port_idx, change.value, change.generation);
}

Status PluginHostLV2::connect_port(uint32_t port_idx, BufferPtr buf) {
  _portmap[port_idx] = buf;
  lilv_instance_connect_port(_instance, port_idx, buf);
  return Status::Ok();
}

Status PluginHostLV2::process_block(uint32_t block_size) {
  //PerfTracker tracker(ctxt->perf.get(), "lv2");

  for (auto& it : _rt_control_values) {
    ControlValue* new_value = ((ControlValue*)_portmap[it.first]);
    ControlValue* old_value = &it.second;
    if (new_value->generation > old_value->generation) {
      ControlValueChange change = { it.first, new_value->value, new_value->generation };
      _control_value_pump.push(change);
      old_value->value = new_value->value;
      old_value->generation = new_value->generation;
    }
  }

  lilv_instance_run(_instance, block_size);
  return Status::Ok();
}

LV2_State_Status PluginHostLV2::store_property(
    LV2_State_Handle handle,
    uint32_t key,
    const void* value,
    size_t size,
    uint32_t type,
    uint32_t flags) {
  StoreContext* ctxt = (StoreContext*)handle;

  const char* key_uri = ctxt->host_system->lv2->unmap(key);
  if (key_uri == nullptr) {
    ctxt->logger->warning("Failed to unmap key URID %u", key);
    return LV2_STATE_ERR_UNKNOWN;
  }

  const char* type_uri = ctxt->host_system->lv2->unmap(type);
  if (type_uri == nullptr) {
    ctxt->logger->warning("Failed to unmap type URID %u", type);
    return LV2_STATE_ERR_UNKNOWN;
  }

  if (!(flags & LV2_STATE_IS_PORTABLE)) {
    ctxt->logger->warning("Property %s is not portable", key_uri);
    return LV2_STATE_ERR_BAD_FLAGS;
  }

  if (!(flags & LV2_STATE_IS_POD)) {
    ctxt->logger->warning("Property %s is not a POD", key_uri);
    return LV2_STATE_ERR_BAD_FLAGS;
  }

  pb::PluginStateLV2* lv2_state = ctxt->state->mutable_lv2();
  pb::PluginStateLV2Property* prop = lv2_state->add_properties();
  prop->set_key(key_uri);
  prop->set_type(type_uri);
  prop->set_value((const char*)value, size);

  return LV2_STATE_SUCCESS;
}

bool PluginHostLV2::has_state() const {
  return _state_interface != nullptr;
}

StatusOr<string> PluginHostLV2::get_state() {
  if (_state_interface == nullptr) {
    return ERROR_STATUS("Plugin does not support the state interface.");
  }

  pb::PluginState state;

  StoreContext ctxt;
  ctxt.state = &state;
  ctxt.host_system = _host_system;
  ctxt.logger = _logger;

  LV2_State_Status status = _state_interface->save(
      _instance->lv2_handle,
      &PluginHostLV2::store_property,
      &ctxt,
      LV2_STATE_IS_PORTABLE | LV2_STATE_IS_POD,
      nullptr);
  if (status != LV2_STATE_SUCCESS) {
    return ERROR_STATUS("Failed to save state, error code %d", status);
  }

  string serialized_state;
  assert(state.SerializeToString(&serialized_state));
  return serialized_state;
}

const void* PluginHostLV2::retrieve_property(
    LV2_State_Handle handle,
    uint32_t key,
    size_t* size,
    uint32_t* type,
    uint32_t* flags) {
  StoreContext* ctxt = (StoreContext*)handle;

  if (!ctxt->state->has_lv2()) {
    return nullptr;
  }

  const char* key_uri = ctxt->host_system->lv2->unmap(key);
  if (key_uri == nullptr) {
    ctxt->logger->warning("Failed to unmap key URID %u", key);
    return nullptr;
  }

  for (const auto& property : ctxt->state->lv2().properties()) {
    if (strcmp(property.key().c_str(), key_uri) == 0) {
      if (size != nullptr) {
        *size = property.value().size();
      }

      if (type != nullptr) {
        LV2_URID type_urid = ctxt->host_system->lv2->map(property.type().c_str());
        if (type_urid > 0) {
          *type = type_urid;
        } else {
          ctxt->logger->warning("Failed to map type URI %s", property.type().c_str());
        }
      }

      return property.value().c_str();
    }
  }

  return nullptr;
}

Status PluginHostLV2::set_state(const pb::PluginState& state) {
  if (_state_interface == nullptr) {
    return ERROR_STATUS("Plugin does not support the state interface.");
  }

  RetrieveContext ctxt;
  ctxt.state = &state;
  ctxt.host_system = _host_system;
  ctxt.logger = _logger;

  LV2_State_Status status = _state_interface->restore(
      _instance->lv2_handle,
      &PluginHostLV2::retrieve_property,
      &ctxt,
      9,
      nullptr);
  if (status != LV2_STATE_SUCCESS) {
    return ERROR_STATUS("Failed to restre state, error code %d", status);
  }

  return Status::Ok();
}

}
