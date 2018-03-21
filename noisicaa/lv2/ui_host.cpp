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
#include "noisicaa/host_system/host_system.h"
#include "noisicaa/lv2/urid_mapper.h"
#include "noisicaa/lv2/feature_manager.h"
#include "noisicaa/lv2/ui_host.h"

namespace noisicaa {

LV2UIHost::LV2UIHost(
    const string& desc,
    HostSystem* host_system,
    void* handle,
    void (*control_value_change_cb)(void*, uint32_t, float))
  : _logger(LoggerRegistry::get_logger("noisicaa.lv2.ui_host")),
    _host_system(host_system),
    _handle(handle),
    _control_value_change_cb(control_value_change_cb) {
  assert(_desc.ParseFromString(desc));
  assert(_desc.has_plugin());
  assert(_desc.plugin().type() == pb::PluginDescription::LV2);
  assert(_desc.has_ui());
  assert(_desc.has_lv2());
  assert(_desc.lv2().uis_size() > 0);
}

LV2UIHost::~LV2UIHost() {}

bool LV2UIHost::_initialized = false;

Status LV2UIHost::setup() {
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

  const pb::LV2Description& plugin_desc = _desc.lv2();
  int ui_idx;
  for (ui_idx = 0 ; ui_idx < plugin_desc.uis_size() ; ++ui_idx) {
    if (plugin_desc.uis(ui_idx).uri() == plugin_desc.ui_uri()) {
      break;
    }
  }
  assert(ui_idx < plugin_desc.uis_size());
  const pb::LV2Description::UI& ui_desc = plugin_desc.uis(ui_idx);

  _feature_manager.reset(new LV2UIFeatureManager(_host_system, _plug));

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

void LV2UIHost::cleanup() {
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
}

void LV2UIHost::port_write_func(
    uint32_t port_index, uint32_t buffer_size, uint32_t protocol, void const *buffer) {
  if (protocol == 0 || protocol == _urid_floatProtocol) {
    assert(buffer_size == sizeof(float));
    assert(buffer != nullptr);
    float value = *((float*)buffer);
    _control_value_change_cb(_handle, port_index, value);
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

uint32_t LV2UIHost::port_index_func(const char *port_symbol) {
  _logger->info("port_index(%s)", port_symbol);
  return 0;
}

uint32_t LV2UIHost::port_subscribe_func(
    uint32_t port_index, uint32_t protocol, const LV2_Feature *const *features) {
  _logger->info("port_subscribe(%d, %d, %p)", port_index, protocol, features);
  return 0;
}

uint32_t LV2UIHost::port_unsubscribe_func(
    uint32_t port_index, uint32_t protocol, const LV2_Feature *const *features) {
  _logger->info("port_unsubscribe(%d, %d, %p)", port_index, protocol, features);
}

void LV2UIHost::touch_func(uint32_t port_index, bool grabbed) {
  _logger->info("touch(%d, %d)", port_index, grabbed);
}

}  // namespace noisicaa
