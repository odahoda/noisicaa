// -*- mode: c++ -*-

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

#ifndef _NOISICAA_AUDIOPROC_ENGINE_PLUGIN_HOST_LV2_H
#define _NOISICAA_AUDIOPROC_ENGINE_PLUGIN_HOST_LV2_H

#include <functional>
#include <memory>
#include <mutex>
#include <vector>
#include "lilv/lilv.h"
#include "lv2/lv2plug.in/ns/ext/state/state.h"
#include "noisicaa/core/pump.h"
#include "noisicaa/core/slots.h"
#include "noisicaa/core/status.h"
#include "noisicaa/audioproc/engine/plugin_host.h"

namespace noisicaa {

using namespace std;

class LV2PluginFeatureManager;
namespace pb {
class PluginState;
}

class PluginHostLV2 : public PluginHost {
public:
  PluginHostLV2(const pb::PluginInstanceSpec& spec, HostSystem* host_system);
  ~PluginHostLV2() override;

  StatusOr<PluginUIHost*> create_ui(
      void* handle,
      void (*control_value_change_cb)(void*, uint32_t, float, uint32_t)) override;

  Status setup() override;
  void cleanup() override;

  Status connect_port(uint32_t port_idx, BufferPtr buf) override;
  Status process_block(uint32_t block_size) override;

  bool has_state() const override;
  StatusOr<string> get_state() override;
  Status set_state(const pb::PluginState& state) override;

  LV2_Handle handle() const { return _instance->lv2_handle; }
  Slot<int, float, uint32_t>::Listener subscribe_to_control_value_changes(
      function<void(int, float, uint32_t)> callback);
  void unsubscribe_from_control_value_changes(Slot<int, float, uint32_t>::Listener listener);

private:
  struct RetrieveContext {
    const pb::PluginState* state;
    HostSystem* host_system;
    Logger* logger;
  };
  static const void* retrieve_property(
      LV2_State_Handle handle,
      uint32_t key,
      size_t* size,
      uint32_t* type,
      uint32_t* flags);

  struct StoreContext {
    pb::PluginState* state;
    HostSystem* host_system;
    Logger* logger;
  };
  static LV2_State_Status store_property(
      LV2_State_Handle handle,
      uint32_t key,
      const void* value,
      size_t size,
      uint32_t type,
      uint32_t flags);

  unique_ptr<LV2PluginFeatureManager> _feature_manager;
  const LilvPlugin* _plugin = nullptr;
  LilvInstance* _instance = nullptr;
  LV2_State_Interface* _state_interface = nullptr;

  vector<BufferPtr> _portmap;

  struct ControlValue {
    float value;
    uint32_t generation;
  };

  struct ControlValueChange {
    int port_idx;
    float value;
    uint32_t generation;
  };

  map<int, ControlValue> _rt_control_values;
  Pump<ControlValueChange> _control_value_pump;
  void control_value_change(const ControlValueChange& change);
  mutex _control_values_mutex;
  map<int, ControlValue> _control_values;
  Slot<int, float, uint32_t> _control_value_changed;
};

}  // namespace noisicaa

#endif
