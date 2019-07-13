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

#ifndef _NOISICAA_BUILTIN_NODES_MIDI_VELOCITY_MAPPER_PROCESSOR_H
#define _NOISICAA_BUILTIN_NODES_MIDI_VELOCITY_MAPPER_PROCESSOR_H

#include <stdint.h>
#include <atomic>
#include "noisicaa/core/status.h"
#include "noisicaa/audioproc/engine/processor.h"

namespace noisicaa {

using namespace std;

class HostSystem;

namespace pb {
class MidiVelocityMapperSpec;
}

class ProcessorMidiVelocityMapper : public Processor {
public:
  ProcessorMidiVelocityMapper(
      const string& realm_name, const string& node_id, HostSystem* host_system,
      const pb::NodeDescription& desc);

protected:
  Status setup_internal() override;
  void cleanup_internal() override;
  Status set_parameters_internal(const pb::NodeParameters& parameters);
  Status process_block_internal(BlockContext* ctxt, TimeMapper* time_mapper) override;

private:
  Status set_spec(const pb::MidiVelocityMapperSpec& spec);

  LV2_Atom_Forge _out_forge;

  atomic<pb::MidiVelocityMapperSpec*> _next_spec;
  atomic<pb::MidiVelocityMapperSpec*> _current_spec;
  atomic<pb::MidiVelocityMapperSpec*> _old_spec;
};

}  // namespace noisicaa

#endif
