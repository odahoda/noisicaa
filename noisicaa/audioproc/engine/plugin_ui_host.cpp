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

#include "noisicaa/core/logging.h"
#include "noisicaa/host_system/host_system.h"
#include "noisicaa/audioproc/engine/plugin_host.h"
#include "noisicaa/audioproc/engine/plugin_ui_host.h"

namespace noisicaa {

PluginUIHost::PluginUIHost(
    PluginHost* plugin,
    HostSystem* host_system,
    void* handle,
    void (*control_value_change_cb)(void*, uint32_t, float, uint32_t),
    const char* logger_name)
  : _logger(LoggerRegistry::get_logger(logger_name)),
    _host_system(host_system),
    _plugin(plugin),
    _handle(handle),
    _control_value_change_cb(control_value_change_cb) {}

PluginUIHost::~PluginUIHost() {}

Status PluginUIHost::setup() {
  _logger->info("Setting up plugin ui host %s...", _plugin->node_id().c_str());

  return Status::Ok();
}

void PluginUIHost::cleanup() {
  _logger->info("Plugin ui host %s cleaned up.", _plugin->node_id().c_str());
}

}  // namespace noisicaa
