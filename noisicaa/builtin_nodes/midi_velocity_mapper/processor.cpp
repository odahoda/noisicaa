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

#include <math.h>

#include "noisicaa/audioproc/engine/misc.h"
#include "noisicaa/audioproc/public/musical_time.h"
#include "noisicaa/audioproc/public/engine_notification.pb.h"
#include "noisicaa/audioproc/public/transfer_function.h"
#include "noisicaa/audioproc/engine/message_queue.h"
#include "noisicaa/host_system/host_system.h"
#include "noisicaa/builtin_nodes/midi_velocity_mapper/processor.h"
#include "noisicaa/builtin_nodes/midi_velocity_mapper/processor.pb.h"

namespace noisicaa {

ProcessorMidiVelocityMapper::ProcessorMidiVelocityMapper(
    const string& realm_name, const string& node_id, HostSystem *host_system,
    const pb::NodeDescription& desc)
  : Processor(
      realm_name, node_id, "noisicaa.audioproc.engine.processor.midi_velocity_mapper", host_system, desc),
    _next_spec(nullptr),
    _current_spec(nullptr),
    _old_spec(nullptr) {
  lv2_atom_forge_init(&_out_forge, &_host_system->lv2->urid_map);
}

Status ProcessorMidiVelocityMapper::setup_internal() {
  return Processor::setup_internal();
}

void ProcessorMidiVelocityMapper::cleanup_internal() {
  pb::MidiVelocityMapperSpec* spec = _next_spec.exchange(nullptr);
  if (spec != nullptr) {
    delete spec;
  }
  spec = _current_spec.exchange(nullptr);
  if (spec != nullptr) {
    delete spec;
  }
  spec = _old_spec.exchange(nullptr);
  if (spec != nullptr) {
    delete spec;
  }

  Processor::cleanup_internal();
}

Status ProcessorMidiVelocityMapper::set_parameters_internal(const pb::NodeParameters& parameters) {
  if (parameters.HasExtension(pb::midi_velocity_mapper_spec)) {
    const auto& spec = parameters.GetExtension(pb::midi_velocity_mapper_spec);

    Status status = set_spec(spec);
    if (status.is_error()) {
      _logger->warning("Failed to update spec: %s", status.message());
    }
  }

  return Processor::set_parameters_internal(parameters);
}

Status ProcessorMidiVelocityMapper::process_block_internal(BlockContext* ctxt, TimeMapper* time_mapper) {
  // If there is a next spec, make it the current. The current spec becomes the old spec, which will
  // eventually be destroyed in the main thread.  It must not happen that a next spec is available,
  // before an old one has been disposed of.
  pb::MidiVelocityMapperSpec* spec = _next_spec.exchange(nullptr);
  if (spec != nullptr) {
    pb::MidiVelocityMapperSpec* old_spec = _current_spec.exchange(spec);
    old_spec = _old_spec.exchange(old_spec);
    assert(old_spec == nullptr);
  }

  spec = _current_spec.load();
  if (spec == nullptr) {
    // No spec yet, just clear my output ports.
    clear_all_outputs();
    return Status::Ok();
  }

  LV2_Atom_Forge_Frame frame;
  lv2_atom_forge_set_buffer(&_out_forge, _buffers[1], 10240);

  lv2_atom_forge_sequence_head(&_out_forge, &frame, _host_system->lv2->urid.atom_frame_time);

  LV2_Atom_Sequence* seq = (LV2_Atom_Sequence*)_buffers[0];
  if (seq->atom.type != _host_system->lv2->urid.atom_sequence) {
    return ERROR_STATUS(
        "Excepted sequence in port 'in', got %d.", seq->atom.type);
  }
  LV2_Atom_Event* event = lv2_atom_sequence_begin(&seq->body);
  while (!lv2_atom_sequence_is_end(&seq->body, seq->atom.size, event)) {
    LV2_Atom& atom = event->body;
    if (atom.type == _host_system->lv2->urid.midi_event) {
      uint8_t midi[3];
      memmove(midi, (uint8_t*)LV2_ATOM_CONTENTS(LV2_Atom, &atom), 3);

      if ((midi[0] & 0xf0) == 0x90) {
        float velocity = (float)midi[2];
        velocity = apply_transfer_function(spec->transfer_function(), velocity);
        midi[2] = max(0, min(127, (int)roundf(velocity)));
      }

      lv2_atom_forge_frame_time(&_out_forge, event->time.frames);
      lv2_atom_forge_atom(&_out_forge, 3, _host_system->lv2->urid.midi_event);
      lv2_atom_forge_write(&_out_forge, midi, 3);
    } else {
      _logger->warning("Ignoring event %d in sequence.", atom.type);
    }

    event = lv2_atom_sequence_next(event);
  }

  lv2_atom_forge_pop(&_out_forge, &frame);

  return Status::Ok();
}

Status ProcessorMidiVelocityMapper::set_spec(const pb::MidiVelocityMapperSpec& spec) {
  _logger->info("Setting spec:\n%s", spec.DebugString().c_str());

  // Discard any next spec, which hasn't been picked up by the audio thread.
  pb::MidiVelocityMapperSpec* prev_next_spec = _next_spec.exchange(nullptr);
  if (prev_next_spec != nullptr) {
    delete prev_next_spec;
  }

  // Discard spec, which the audio thread doesn't use anymore.
  pb::MidiVelocityMapperSpec* old_spec = _old_spec.exchange(nullptr);
  if (old_spec != nullptr) {
    delete old_spec;
  }

  // Create the new spec.
  unique_ptr<pb::MidiVelocityMapperSpec> new_spec(new pb::MidiVelocityMapperSpec());
  new_spec->CopyFrom(spec);

  // Make the new spec the next one for the audio thread.
  prev_next_spec = _next_spec.exchange(new_spec.release());
  assert(prev_next_spec == nullptr);

  return Status::Ok();
}

}
