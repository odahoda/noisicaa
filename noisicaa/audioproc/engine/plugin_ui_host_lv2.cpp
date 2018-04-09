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

#include <assert.h>
#include <string>
#include "gtk/gtk.h"
#include "suil/suil.h"
#include "lv2/lv2plug.in/ns/extensions/ui/ui.h"
#include "noisicaa/core/logging.h"
#include "noisicaa/core/slots.inl.h"
#include "noisicaa/host_system/host_system.h"
#include "noisicaa/lv2/urid_mapper.h"
#include "noisicaa/lv2/feature_manager.h"
#include "noisicaa/audioproc/engine/plugin_host_lv2.h"
#include "noisicaa/audioproc/engine/plugin_ui_host_lv2.h"


namespace noisicaa {

PluginUIHostLV2::PluginUIHostLV2(
    PluginHostLV2* plugin,
    HostSystem* host_system,
    void* handle,
    void (*control_value_change_cb)(void*, uint32_t, float, uint32_t))
  : PluginUIHost(
      plugin, host_system,
      handle, control_value_change_cb,
      "noisicaa.audioproc.engine.plugin_ui_host_lv2"),
    _plugin(plugin),
    _plugin_handle(_plugin->handle()) {
  const pb::NodeDescription& desc = plugin->description();
  assert(desc.has_plugin());
  assert(desc.plugin().type() == pb::PluginDescription::LV2);
  assert(desc.has_ui());
  assert(desc.has_lv2());
  assert(desc.lv2().uis_size() > 0);
}

bool PluginUIHostLV2::_initialized = false;

Status PluginUIHostLV2::setup() {
  RETURN_IF_ERROR(PluginUIHost::setup());

  if (!_initialized) {
    _logger->info("Initialize suil...");
    suil_init(nullptr, nullptr, SUIL_ARG_NONE);
    _initialized = true;
  }

  _urid_floatProtocol = _host_system->lv2->urid_mapper()->map(LV2_UI__floatProtocol);

  _logger->info("Creating suil host...");
  _host = suil_host_new(
      port_write_proxy,
      port_index_proxy,
      port_subscribe_proxy,
      port_unsubscribe_proxy);
  if (_host == nullptr) {
    return ERROR_STATUS("Failed to create suil host.");
  }
  suil_host_set_touch_func(_host, touch_proxy);

  _logger->info("Creating GtkPlug widget...");

  _plug = gtk_plug_new(0);
  if (_plug == nullptr) {
    return ERROR_STATUS("Failed to create GtkPlug.");
  }

  _logger->info("Creating suil instance...");

  const pb::LV2Description& plugin_desc = _plugin->description().lv2();
  int ui_idx;
  for (ui_idx = 0 ; ui_idx < plugin_desc.uis_size() ; ++ui_idx) {
    if (plugin_desc.uis(ui_idx).uri() == plugin_desc.ui_uri()) {
      break;
    }
  }
  assert(ui_idx < plugin_desc.uis_size());
  const pb::LV2Description::UI& ui_desc = plugin_desc.uis(ui_idx);

  _feature_manager.reset(new LV2UIFeatureManager(_host_system, _plug, _plugin_handle));

  _instance = suil_instance_new(
      _host,
      (SuilController)this,
      "http://lv2plug.in/ns/extensions/ui#GtkUI",
      plugin_desc.uri().c_str(),
      ui_desc.uri().c_str(),
      ui_desc.type_uri().c_str(),
      ui_desc.bundle_path().c_str(),
      ui_desc.binary_path().c_str(),
      _feature_manager->get_features());
  if (_instance == nullptr) {
    return ERROR_STATUS("Failed to create suil instance.");
  }

  _control_values.resize(_plugin->description().ports_size());
  for (size_t idx = 0 ; idx < _control_values.size() ; ++idx) {
    _control_values[idx] = ControlValue{ 0.0, 0 };
  }

  _control_value_change_listener = _plugin->subscribe_to_control_value_changes(
      bind(&PluginUIHostLV2::control_value_changed, this,
           placeholders::_1, placeholders::_2, placeholders::_3));

  _logger->info("Attaching plugin widget...");
  GtkWidget* plug_widget = (GtkWidget*)suil_instance_get_widget(_instance);
  assert(plug_widget != nullptr);

  gtk_container_add(GTK_CONTAINER(_plug), plug_widget);
  gtk_widget_show_all(_plug);

  GtkAllocation alloc;
  gtk_widget_get_allocation(plug_widget, &alloc);

  _wid = gtk_plug_get_id(GTK_PLUG(_plug));
  _width = alloc.width;
  _height = alloc.height;

  return Status::Ok();
}

void PluginUIHostLV2::cleanup() {
  if (_control_value_change_listener != 0) {
    _plugin->unsubscribe_from_control_value_changes(_control_value_change_listener);
    _control_value_change_listener = 0;
  }

  _control_values.clear();

  if (_instance != nullptr) {
    _logger->info("Cleaning up suil instance...");
    suil_instance_free(_instance);
    _instance = nullptr;
  }

  if (_feature_manager.get() != nullptr) {
    _logger->info("Cleaning up LV2UIFeatureManager...");
    _feature_manager.reset();
  }

  if (_plug != nullptr) {
    _logger->info("Cleaning up GtkPlug widget...");
    gtk_widget_destroy(_plug);
    _plug = nullptr;
  }

  if (_host != nullptr) {
    _logger->info("Cleaning up suil host...");
    suil_host_free(_host);
    _host = nullptr;
  }

  PluginUIHost::cleanup();
}

void PluginUIHostLV2::control_value_changed(int port_idx, float value, uint32_t generation) {
  _logger->info("control_value_changed(%d, %f, %d)", port_idx, value, generation);
  if (generation > _control_values[port_idx].generation) {
    _control_values[port_idx] = ControlValue{ value, generation };
    suil_instance_port_event(_instance, port_idx, sizeof(float), 0, &value);
  }
}

void PluginUIHostLV2::port_write_func(
    uint32_t port_index, uint32_t buffer_size, uint32_t protocol, void const *buffer) {
  if (protocol == 0 || protocol == _urid_floatProtocol) {
    assert(buffer_size == sizeof(float));
    assert(buffer != nullptr);
    float value = *((float*)buffer);
    if (value != _control_values[port_index].value) {
      _control_values[port_index].value = value;
      ++_control_values[port_index].generation;
      control_value_change(port_index, value, _control_values[port_index].generation);
    }
  } else {
    _logger->info("port_write(%d, %d, %d, %p)", port_index, buffer_size, protocol, buffer);

    const char* protocol_uri = _host_system->lv2->urid_mapper()->unmap(protocol);
    if (protocol_uri != nullptr) {
      _logger->warning("Unsupported protocol %s", protocol_uri);
    } else {
      _logger->warning("Unsupported protocol %d", protocol);
    }
  }
}

uint32_t PluginUIHostLV2::port_index_func(const char *port_symbol) {
  _logger->info("port_index(%s)", port_symbol);
  return 0;
}

uint32_t PluginUIHostLV2::port_subscribe_func(
    uint32_t port_index, uint32_t protocol, const LV2_Feature *const *features) {
  _logger->info("port_subscribe(%d, %d, %p)", port_index, protocol, features);
  return 0;
}

uint32_t PluginUIHostLV2::port_unsubscribe_func(
    uint32_t port_index, uint32_t protocol, const LV2_Feature *const *features) {
  _logger->info("port_unsubscribe(%d, %d, %p)", port_index, protocol, features);
  return 0;
}

void PluginUIHostLV2::touch_func(uint32_t port_index, bool grabbed) {
  _logger->info("touch(%d, %d)", port_index, grabbed);
}

}  // namespace noisicaa
