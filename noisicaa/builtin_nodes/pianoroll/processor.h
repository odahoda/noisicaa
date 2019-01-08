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

#ifndef _NOISICAA_BUILTIN_NODES_PIANOROLL_PROCESSOR_H
#define _NOISICAA_BUILTIN_NODES_PIANOROLL_PROCESSOR_H

#include <stdint.h>
#include <atomic>
#include <memory>
#include <vector>
#include "lv2/lv2plug.in/ns/ext/atom/forge.h"
#include "noisicaa/core/status.h"
#include "noisicaa/audioproc/public/musical_time.h"
#include "noisicaa/audioproc/engine/buffers.h"
#include "noisicaa/audioproc/engine/double_buffered_state_manager.h"
#include "noisicaa/audioproc/engine/processor.h"


namespace noisicaa {

class BlockContext;
class HostSystem;

namespace pb {
class ProcessorMessage;
class PianoRollAddInterval;
class PianoRollRemoveInterval;
}

class PianoRollEvent {
public:
  uint64_t id;

  MusicalTime time;

  enum Type {
    // Events emitted at the same sample are sorted by type (e.g. first all noteoffs,
    // before any noteons are emitted).

    NOTE_OFF = 1,
    NOTE_ON,
  };
  Type type;

  uint8_t pitch;
  uint8_t velocity;

  string to_string() const;
};

class PianoRoll : public ManagedState<pb::ProcessorMessage> {
public:
  vector<PianoRollEvent> events;

  int offset = -1;
  MusicalTime current_time = MusicalTime(0, 1);

  void apply_mutation(pb::ProcessorMessage* msg) override;

private:
  void add_event(const PianoRollEvent& event);
  void remove_events(uint64_t id);

  void apply_add_interval(const pb::PianoRollAddInterval& msg);
  void apply_remove_interval(const pb::PianoRollRemoveInterval& msg);
};

class ProcessorPianoRoll : public Processor {
public:
  ProcessorPianoRoll(
      const string& realm_name, const string& node_id, HostSystem* host_system,
      const pb::NodeDescription& desc);
  ~ProcessorPianoRoll() override;

protected:
  Status setup_internal() override;
  void cleanup_internal() override;
  Status handle_message_internal(pb::ProcessorMessage* msg) override;
  Status connect_port_internal(BlockContext* ctxt, uint32_t port_idx, BufferPtr buf) override;
  Status process_block_internal(BlockContext* ctxt, TimeMapper* time_mapper) override;

private:
  void note_on(LV2_Atom_Forge* forge, uint32_t sample, uint8_t pitch, uint8_t velocity);
  void note_off(LV2_Atom_Forge* forge, uint32_t sample, uint8_t pitch);

  BufferPtr _out_buffer;

  uint8_t _active_notes[128];

  DoubleBufferedStateManager<PianoRoll, pb::ProcessorMessage> _pianoroll_manager;
};

}  // namespace noisicaa

#endif
