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
#include "noisicaa/audioproc/engine/message_queue.h"
#include "noisicaa/host_system/host_system.h"
#include "noisicaa/builtin_nodes/midi_looper/processor.h"
#include "noisicaa/builtin_nodes/midi_looper/processor.pb.h"
#include "noisicaa/builtin_nodes/midi_looper/model.pb.h"

namespace noisicaa {

ProcessorMidiLooper::ProcessorMidiLooper(
    const string& realm_name, const string& node_id, HostSystem *host_system,
    const pb::NodeDescription& desc)
  : Processor(
      realm_name, node_id, "noisicaa.audioproc.engine.processor.midi_looper", host_system, desc),
    _next_spec(nullptr),
    _current_spec(nullptr),
    _old_spec(nullptr) {
  _current_position_urid = _host_system->lv2->map(
      "http://noisicaa.odahoda.de/lv2/processor_midi_looper#current_position");
  lv2_atom_forge_init(&_node_msg_forge, &_host_system->lv2->urid_map);
}

Status ProcessorMidiLooper::setup_internal() {
  RETURN_IF_ERROR(Processor::setup_internal());

  _buffers.resize(_desc.ports_size());

  return Status::Ok();
}

void ProcessorMidiLooper::cleanup_internal() {
  pb::MidiLooperSpec* spec = _next_spec.exchange(nullptr);
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

  _buffers.clear();

  Processor::cleanup_internal();
}

Status ProcessorMidiLooper::set_parameters_internal(const pb::NodeParameters& parameters) {
  if (parameters.HasExtension(pb::midi_looper_spec)) {
    const auto& spec = parameters.GetExtension(pb::midi_looper_spec);

    Status status = set_spec(spec);
    if (status.is_error()) {
      _logger->warning("Failed to update spec: %s", status.message());
    }
  }

  return Processor::set_parameters_internal(parameters);
}

Status ProcessorMidiLooper::connect_port_internal(
    BlockContext* ctxt, uint32_t port_idx, BufferPtr buf) {
  if (port_idx >= _buffers.size()) {
    return ERROR_STATUS("Invalid port index %d", port_idx);
  }
  _buffers[port_idx] = buf;
  return Status::Ok();
}

Status ProcessorMidiLooper::process_block_internal(BlockContext* ctxt, TimeMapper* time_mapper) {
  // If there is a next spec, make it the current. The current spec becomes the old spec, which will
  // eventually be destroyed in the main thread.  It must not happen that a next spec is available,
  // before an old one has been disposed of.
  pb::MidiLooperSpec* spec = _next_spec.exchange(nullptr);
  if (spec != nullptr) {
    pb::MidiLooperSpec* old_spec = _current_spec.exchange(spec);
    old_spec = _old_spec.exchange(old_spec);
    assert(old_spec == nullptr);
  }

  spec = _current_spec.load();
  if (spec == nullptr) {
    // No spec yet, just clear my output ports.
    clear_all_outputs();
    return Status::Ok();
  }

  MusicalDuration duration = MusicalDuration(spec->duration());

  SampleTime* stime = ctxt->time_map.get();
  for (uint32_t pos = 0; pos < _host_system->block_size(); ++pos, ++stime) {
    if (stime->start_time.numerator() < 0) {
      continue;
    }

    MusicalTime current_position = stime->start_time % duration;

    if (pos == 0) {
      uint8_t atom[10000];
      lv2_atom_forge_set_buffer(&_node_msg_forge, atom, sizeof(atom));

      LV2_Atom_Forge_Frame frame;
      lv2_atom_forge_object(&_node_msg_forge, &frame, _host_system->lv2->urid.core_nodemsg, 0);
      lv2_atom_forge_key(&_node_msg_forge, _current_position_urid);
      LV2_Atom_Forge_Frame tframe;
      lv2_atom_forge_tuple(&_node_msg_forge, &tframe);
      lv2_atom_forge_int(&_node_msg_forge, current_position.numerator());
      lv2_atom_forge_int(&_node_msg_forge, current_position.denominator());
      lv2_atom_forge_pop(&_node_msg_forge, &tframe);
      lv2_atom_forge_pop(&_node_msg_forge, &frame);

      NodeMessage::push(ctxt->out_messages, _node_id, (LV2_Atom*)atom);
    }
  }

  clear_all_outputs();
  return Status::Ok();
}

Status ProcessorMidiLooper::set_spec(const pb::MidiLooperSpec& spec) {
  _logger->info("Setting spec:\n%s", spec.DebugString().c_str());

  // Discard any next spec, which hasn't been picked up by the audio thread.
  pb::MidiLooperSpec* prev_next_spec = _next_spec.exchange(nullptr);
  if (prev_next_spec != nullptr) {
    delete prev_next_spec;
  }

  // Discard spec, which the audio thread doesn't use anymore.
  pb::MidiLooperSpec* old_spec = _old_spec.exchange(nullptr);
  if (old_spec != nullptr) {
    delete old_spec;
  }

  // Create the new spec.
  unique_ptr<pb::MidiLooperSpec> new_spec(new pb::MidiLooperSpec());
  new_spec->CopyFrom(spec);

  // Make the new spec the next one for the audio thread.
  prev_next_spec = _next_spec.exchange(new_spec.release());
  assert(prev_next_spec == nullptr);

  return Status::Ok();
}

}
