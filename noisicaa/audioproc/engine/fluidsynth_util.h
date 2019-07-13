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

#ifndef _NOISICAA_AUDIOPROC_ENGINE_FLUIDSYNTH_UTIL_H
#define _NOISICAA_AUDIOPROC_ENGINE_FLUIDSYNTH_UTIL_H

#include <stdint.h>
#include <string>
#include <vector>
#include "fluidsynth.h"
#include "noisicaa/core/status.h"
#include "noisicaa/audioproc/engine/buffers.h"

namespace noisicaa {

using namespace std;

class Logger;
class HostSystem;
class BlockContext;
class TimeMapper;

class FluidSynthUtil {
public:
  FluidSynthUtil(HostSystem* host_system);
  ~FluidSynthUtil();

  Status setup(const string& path, uint32_t bank, uint32_t preset);
  Status process_block(BlockContext* ctxt, TimeMapper* time_mapper, vector<Buffer*>& buffers);

private:
  Logger* _logger;
  HostSystem* _host_system;

  fluid_settings_t* _settings = nullptr;
  fluid_synth_t* _synth = nullptr;
};

}  // namespace noisicaa

#endif
