// -*- mode: c++ -*-

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

#ifndef _NOISICAA_AUDIOPROC_ENGINE_PLUGIN_UI_HOST_LV2_H
#define _NOISICAA_AUDIOPROC_ENGINE_PLUGIN_UI_HOST_LV2_H

#include <memory>
#include "lv2/lv2plug.in/ns/lv2core/lv2.h"
#include "suil/suil.h"
#include "noisicaa/core/status.h"
#include "noisicaa/audioproc/engine/plugin_ui_host.h"

struct _GtkWidget;
typedef _GtkWidget GtkWidget;

namespace noisicaa {

using namespace std;

class HostSystem;
class PluginHostLV2;
class LV2UIFeatureManager;
class URIDMapper;

class PluginUIHostLV2 : public PluginUIHost {
public:
  PluginUIHostLV2(
      PluginHostLV2* plugin,
      HostSystem* host_system,
      void* handle,
      void (*control_value_change_cb)(void*, uint32_t, float));

  Status setup() override;
  void cleanup() override;

  unsigned long int wid() const override { return _wid; }
  int width() const override { return _width; }
  int height() const override { return _height; }

private:
  void port_write_func(
      uint32_t port_index, uint32_t buffer_size, uint32_t protocol, void const *buffer);
  static void port_write_proxy(
      SuilController controller, uint32_t port_index, uint32_t buffer_size, uint32_t protocol,
      void const *buffer) {
    PluginUIHostLV2* self = (PluginUIHostLV2*)controller;
    self->port_write_func(port_index, buffer_size, protocol, buffer);
  }

  uint32_t port_index_func(const char *port_symbol);
  static uint32_t port_index_proxy(SuilController controller, const char *port_symbol) {
    PluginUIHostLV2* self = (PluginUIHostLV2*)controller;
    return self->port_index_func(port_symbol);
  }

  uint32_t port_subscribe_func(
      uint32_t port_index, uint32_t protocol, const LV2_Feature *const *features);
  static uint32_t port_subscribe_proxy(
      SuilController controller, uint32_t port_index, uint32_t protocol,
      const LV2_Feature *const *features) {
    PluginUIHostLV2* self = (PluginUIHostLV2*)controller;
    return self->port_subscribe_func(port_index, protocol, features);
  }

  uint32_t port_unsubscribe_func(
      uint32_t port_index, uint32_t protocol, const LV2_Feature *const *features);
  static uint32_t port_unsubscribe_proxy(
      SuilController controller, uint32_t port_index, uint32_t protocol,
      const LV2_Feature *const *features) {
    PluginUIHostLV2* self = (PluginUIHostLV2*)controller;
    return self->port_unsubscribe_func(port_index, protocol, features);
  }

  void touch_func(uint32_t port_index, bool grabbed);
  static void touch_proxy(SuilController controller, uint32_t port_index, bool grabbed) {
    PluginUIHostLV2* self = (PluginUIHostLV2*)controller;
    self->touch_func(port_index, grabbed);
  }

  static bool _initialized;

  LV2_URID _urid_floatProtocol;

  LV2_Handle _plugin_handle = nullptr;

  unsigned long int _wid = 0;
  int _width = -1;
  int _height = -1;

  unique_ptr<LV2UIFeatureManager> _feature_manager;
  SuilHost* _host = nullptr;
  SuilInstance* _instance = nullptr;

  GtkWidget* _plug = nullptr;
};

}  // namespace noisicaa

#endif
