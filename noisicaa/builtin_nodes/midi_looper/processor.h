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

#ifndef _NOISICAA_BUILTIN_NODES_MIDI_LOOPER_PROCESSOR_H
#define _NOISICAA_BUILTIN_NODES_MIDI_LOOPER_PROCESSOR_H

#include <stdint.h>
#include <atomic>
#include <memory>
#include <vector>
#include "lv2/lv2plug.in/ns/ext/urid/urid.h"
#include "noisicaa/core/status.h"
#include "noisicaa/audioproc/engine/processor.h"

namespace noisicaa {

using namespace std;

class HostSystem;

namespace pb {
class MidiLooperSpec;
}

class ProcessorMidiLooper : public Processor {
public:
  ProcessorMidiLooper(
      const string& realm_name, const string& node_id, HostSystem* host_system,
      const pb::NodeDescription& desc);

protected:
  Status setup_internal() override;
  void cleanup_internal() override;
  Status handle_message_internal(pb::ProcessorMessage* msg) override;
  Status set_parameters_internal(const pb::NodeParameters& parameters);
  Status connect_port_internal(BlockContext* ctxt, uint32_t port_idx, BufferPtr buf) override;
  Status process_block_internal(BlockContext* ctxt, TimeMapper* time_mapper) override;

private:
  Status set_spec(const pb::MidiLooperSpec& spec);
  Status process_sample(uint32_t pos, const MusicalTime sstart, const MusicalTime send);
  void post_record_state(BlockContext* ctxt);

  LV2_URID _current_position_urid;
  LV2_URID _record_state_urid;
  LV2_Atom_Forge _node_msg_forge;
  LV2_Atom_Forge _out_forge;

  vector<BufferPtr> _buffers;

  // Keep this in sync with RecordState in node_ui.py
  enum RecordState {
    UNSET = 0,
    OFF = 1,
    WAITING = 2,
    RECORDING = 3,
  };
  atomic<RecordState> _next_record_state;
  RecordState _record_state;

  struct RecordedEvent {
    MusicalTime time;
    uint8_t midi[3];
  };
  static const uint32_t _recorded_max_count = 1000;
  RecordedEvent _recorded_events[_recorded_max_count];
  uint32_t _recorded_count;

  MusicalTime _playback_pos;
  uint32_t _playback_index;

  atomic<pb::MidiLooperSpec*> _next_spec;
  atomic<pb::MidiLooperSpec*> _current_spec;
  atomic<pb::MidiLooperSpec*> _old_spec;
};

}  // namespace noisicaa

#endif
