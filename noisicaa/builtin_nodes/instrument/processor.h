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

#ifndef _NOISICAA_BUILTIN_NODES_INSTRUMENT_PROCESSOR_H
#define _NOISICAA_BUILTIN_NODES_INSTRUMENT_PROCESSOR_H

#include <atomic>
#include <memory>
#include <vector>
#include "noisicaa/core/status.h"
#include "noisicaa/audioproc/engine/processor.h"

namespace noisicaa {

using namespace std;

class HostSystem;
class CSoundUtil;
class FluidSynthUtil;

namespace pb {
class InstrumentSpec;
}

class ProcessorInstrument : public Processor {
public:
  ProcessorInstrument(
      const string& realm_name, const string& node_id, HostSystem* host_system,
      const pb::NodeDescription& desc);

protected:
  Status setup_internal() override;
  void cleanup_internal() override;
  Status handle_message_internal(pb::ProcessorMessage* msg) override;
  Status connect_port_internal(BlockContext* ctxt, uint32_t port_idx, BufferPtr buf) override;
  Status process_block_internal(BlockContext* ctxt, TimeMapper* time_mapper) override;

private:
  Status change_instrument(const pb::InstrumentSpec& spec);
  void csound_log(LogLevel log_level, const char* msg);

  vector<BufferPtr> _buffers;

  struct Instrument {
    unique_ptr<FluidSynthUtil> fluidsynth;
    unique_ptr<CSoundUtil> csound;
  };

  atomic<Instrument*> _next_instrument;
  atomic<Instrument*> _current_instrument;
  atomic<Instrument*> _old_instrument;
};

}  // namespace noisicaa

#endif
