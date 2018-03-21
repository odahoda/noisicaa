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

#ifndef _NOISICAA_AUDIOPROC_ENGINE_PROCESSOR_FLUIDSYNTH_H
#define _NOISICAA_AUDIOPROC_ENGINE_PROCESSOR_FLUIDSYNTH_H

#include <string>
#include <vector>
#include <stdint.h>
#include "fluidsynth.h"
#include "lv2/lv2plug.in/ns/ext/urid/urid.h"
#include "noisicaa/core/status.h"
#include "noisicaa/audioproc/engine/buffers.h"
#include "noisicaa/audioproc/engine/processor.h"

namespace noisicaa {

using namespace std;

class HostSystem;
class BlockContext;

class ProcessorFluidSynth : public Processor {
public:
  ProcessorFluidSynth(
      const string& node_id, HostSystem* host_system, const pb::NodeDescription& desc);
  ~ProcessorFluidSynth() override;

protected:
  Status setup_internal() override;
  void cleanup_internal() override;
  Status connect_port_internal(BlockContext* ctxt, uint32_t port_idx, BufferPtr buf) override;
  Status process_block_internal(BlockContext* ctxt, TimeMapper* time_mapper) override;

private:
  BufferPtr _buffers[3];

  fluid_settings_t* _settings = nullptr;
  fluid_synth_t* _synth = nullptr;
};

}  // namespace noisicaa

#endif
