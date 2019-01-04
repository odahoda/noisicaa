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

#include "noisicaa/audioproc/engine/backend.h"
#include "noisicaa/audioproc/engine/backend_null.h"
#include "noisicaa/audioproc/engine/backend_portaudio.h"
#include "noisicaa/audioproc/engine/backend_renderer.h"

namespace noisicaa {

Backend::Backend(HostSystem* host_system, const char* logger_name, const BackendSettings& settings)
  : _host_system(host_system),
    _logger(LoggerRegistry::get_logger(logger_name)),
    _settings(settings) {}

Backend::~Backend() {
  cleanup();
}

StatusOr<Backend*> Backend::create(
    HostSystem* host_system, const string& name, const BackendSettings& settings) {
  if (name == "portaudio") {
    return new PortAudioBackend(host_system, settings);
  } else if (name == "null") {
    return new NullBackend(host_system, settings);
  } else if (name == "renderer") {
    return new RendererBackend(host_system, settings);
  }

  return ERROR_STATUS("Invalid backend name '%s'", name.c_str());
}

Status Backend::setup(Realm* realm) {
  _realm = realm;
  return Status::Ok();
}

void Backend::cleanup() {
}

}  // namespace noisicaa
