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

#include "lv2/lv2plug.in/ns/ext/atom/forge.h"

#include "noisicaa/audioproc/engine/misc.h"
#include "noisicaa/audioproc/public/engine_notification.pb.h"
#include "noisicaa/audioproc/public/processor_message.pb.h"
#include "noisicaa/audioproc/engine/message_queue.h"
#include "noisicaa/host_system/host_system.h"
#include "noisicaa/builtin_nodes/processor_message_registry.pb.h"
#include "noisicaa/builtin_nodes/midi_cc_to_cv/processor.h"
#include "noisicaa/builtin_nodes/midi_cc_to_cv/processor.pb.h"
#include "noisicaa/builtin_nodes/midi_cc_to_cv/processor_messages.pb.h"

namespace noisicaa {

ProcessorMidiCCtoCV::ProcessorMidiCCtoCV(
    const string& realm_name, const string& node_id, HostSystem *host_system,
    const pb::NodeDescription& desc)
  : Processor(
      realm_name, node_id, "noisicaa.audioproc.engine.processor.midi_cc_to_cv", host_system, desc),
    _next_spec(nullptr),
    _current_spec(nullptr),
    _old_spec(nullptr) {
  _learn_urid = _host_system->lv2->map(
      "http://noisicaa.odahoda.de/lv2/processor_cc_to_cv#learn");
}

Status ProcessorMidiCCtoCV::setup_internal() {
  RETURN_IF_ERROR(Processor::setup_internal());

  _buffers.resize(_desc.ports_size());
  for (int idx = 0; idx < 128 ; ++idx) {
    _current_value[idx] = 0.0;
  }
  _learn = 0;

  return Status::Ok();
}

void ProcessorMidiCCtoCV::cleanup_internal() {
  pb::MidiCCtoCVSpec* spec = _next_spec.exchange(nullptr);
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

Status ProcessorMidiCCtoCV::handle_message_internal(pb::ProcessorMessage* msg) {
  unique_ptr<pb::ProcessorMessage> msg_ptr(msg);
  if (msg->HasExtension(pb::midi_cc_to_cv_learn)) {
    const pb::MidiCCtoCVLearn& m = msg->GetExtension(pb::midi_cc_to_cv_learn);
    if (m.enable()) {
      ++_learn;
    } else {
      if (_learn > 0) {
        --_learn;
      } else {
        _logger->error("Unbalanced MidiCCtoCVLearn messages.");
      }
    }

    return Status::Ok();
  }

  return Processor::handle_message_internal(msg_ptr.release());
}

Status ProcessorMidiCCtoCV::set_parameters_internal(const pb::NodeParameters& parameters) {
  if (parameters.HasExtension(pb::midi_cc_to_cv_spec)) {
    const auto& spec = parameters.GetExtension(pb::midi_cc_to_cv_spec);

    Status status = set_spec(spec);
    if (status.is_error()) {
      _logger->warning("Failed to update spec: %s", status.message());
    }
  }

  return Processor::set_parameters_internal(parameters);
}

Status ProcessorMidiCCtoCV::connect_port_internal(
    BlockContext* ctxt, uint32_t port_idx, BufferPtr buf) {
  if (port_idx >= _buffers.size()) {
    return ERROR_STATUS("Invalid port index %d", port_idx);
  }
  _buffers[port_idx] = buf;
  return Status::Ok();
}

Status ProcessorMidiCCtoCV::process_block_internal(BlockContext* ctxt, TimeMapper* time_mapper) {
  // If there is a next sequence, make it the current. The current sequence becomes
  // the old sequence, which will eventually be destroyed in the main thread.
  // It must not happen that a next sequence is available, before an old one has
  // been disposed of.
  pb::MidiCCtoCVSpec* spec = _next_spec.exchange(nullptr);
  if (spec != nullptr) {
    pb::MidiCCtoCVSpec* old_spec = _current_spec.exchange(spec);
    old_spec = _old_spec.exchange(old_spec);
    assert(old_spec == nullptr);
  }

  spec = _current_spec.load();
  if (spec == nullptr) {
    // No sequence yet, just clear my output ports.
    clear_all_outputs();
    return Status::Ok();
  }

  if ((uint32_t)spec->channels_size() + 1 != _buffers.size()) {
    _logger->error(
        "Buffer count does not match spec (%d buffers vs. %d channels)",
        _buffers.size(), spec->channels_size());
    clear_all_outputs();
    return Status::Ok();
  }

  bool learn = _learn > 0;

  LV2_Atom_Sequence* seq = (LV2_Atom_Sequence*)_buffers[0];
  if (seq->atom.type != _host_system->lv2->urid.atom_sequence) {
    return ERROR_STATUS(
        "Excepted sequence in port 'in', got %d.", seq->atom.type);
  }
  LV2_Atom_Event* event = lv2_atom_sequence_begin(&seq->body);

  for (uint32_t pos = 0; pos < _host_system->block_size(); ++pos) {
    while (!lv2_atom_sequence_is_end(&seq->body, seq->atom.size, event)
           && event->time.frames <= pos) {
      LV2_Atom& atom = event->body;
      if (atom.type == _host_system->lv2->urid.midi_event) {
        uint8_t* midi = (uint8_t*)LV2_ATOM_CONTENTS(LV2_Atom, &atom);

        for (int channel_idx = 0 ; channel_idx < spec->channels_size() ; ++channel_idx) {
          const auto& channel_spec = spec->channels(channel_idx);
          if ((midi[0] & 0xf0) == 0xb0
              && (midi[0] & 0x0f) == channel_spec.midi_channel()
              && midi[1] == channel_spec.midi_controller()) {
            _current_value[channel_idx] = midi[2] / 127.0;
          }

          if (learn) {
            uint8_t atom[200];
            LV2_Atom_Forge forge;
            lv2_atom_forge_init(&forge, &_host_system->lv2->urid_map);
            lv2_atom_forge_set_buffer(&forge, atom, sizeof(atom));

            LV2_Atom_Forge_Frame oframe;
            lv2_atom_forge_object(&forge, &oframe, _host_system->lv2->urid.core_nodemsg, 0);

            lv2_atom_forge_key(&forge, _learn_urid);
            LV2_Atom_Forge_Frame tframe;
            lv2_atom_forge_tuple(&forge, &tframe);
            lv2_atom_forge_int(&forge, midi[0] & 0x0f);
            lv2_atom_forge_int(&forge, midi[1]);
            lv2_atom_forge_pop(&forge, &tframe);

            lv2_atom_forge_pop(&forge, &oframe);

            NodeMessage::push(ctxt->out_messages, _node_id, (LV2_Atom*)atom);
          }
        }
      } else {
        _logger->warning("Ignoring event %d in sequence.", atom.type);
      }

      event = lv2_atom_sequence_next(event);
    }

    for (int channel_idx = 0 ; channel_idx < spec->channels_size() ; ++channel_idx) {
      const auto& channel_spec = spec->channels(channel_idx);
      float* out = (float*)_buffers[channel_idx + 1];
      float current_value = _current_value[channel_idx];
      out[pos] = (channel_spec.max_value() - channel_spec.min_value()) * current_value + channel_spec.min_value();
    }
  }

  if (!lv2_atom_sequence_is_end(&seq->body, seq->atom.size, event)) {
    _logger->warning("Ignoring event(s) with invalid frame positions.");
  }

  return Status::Ok();
}

Status ProcessorMidiCCtoCV::set_spec(const pb::MidiCCtoCVSpec& spec) {
  _logger->info("Setting spec:\n%s", spec.DebugString().c_str());

  // Discard any next sequence, which hasn't been picked up by the audio thread.
  pb::MidiCCtoCVSpec* prev_next_spec = _next_spec.exchange(nullptr);
  if (prev_next_spec != nullptr) {
    delete prev_next_spec;
  }

  // Discard sequence, which the audio thread doesn't use anymore.
  pb::MidiCCtoCVSpec* old_spec = _old_spec.exchange(nullptr);
  if (old_spec != nullptr) {
    delete old_spec;
  }

  // Create the new sequence.
  unique_ptr<pb::MidiCCtoCVSpec> new_spec(new pb::MidiCCtoCVSpec());
  new_spec->CopyFrom(spec);

  // Make the new sequence the next one for the audio thread.
  prev_next_spec = _next_spec.exchange(new_spec.release());
  assert(prev_next_spec == nullptr);

  return Status::Ok();
}

}
