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

#ifndef _NOISICAA_AUDIOPROC_ENGINE_PLUGIN_UI_HOST_H
#define _NOISICAA_AUDIOPROC_ENGINE_PLUGIN_UI_HOST_H

#include "noisicaa/core/status.h"
#include "noisicaa/audioproc/engine/buffers.h"
#include "noisicaa/audioproc/engine/plugin_host.pb.h"

namespace noisicaa {

using namespace std;

class Logger;
class HostSystem;
class PluginHost;

class PluginUIHost {
public:
  virtual ~PluginUIHost();

  virtual Status setup();
  virtual void cleanup();

  virtual unsigned long int wid() const = 0;
  virtual int width() const = 0;
  virtual int height() const = 0;

protected:
  PluginUIHost(
      PluginHost* plugin,
      HostSystem* host_system,
      void* handle,
      void (*control_value_change_cb)(void*, uint32_t, float),
      const char* logger_name);

  void control_value_change(uint32_t port_index, float value) {
    _control_value_change_cb(_handle, port_index, value);
  }

  PluginHost* _plugin;
  Logger* _logger;
  HostSystem* _host_system;

private:
  void* _handle;
  void (*_control_value_change_cb)(void*, uint32_t, float);
};

}  // namespace noisicaa

#endif
