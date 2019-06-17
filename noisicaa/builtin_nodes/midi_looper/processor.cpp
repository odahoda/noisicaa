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
#include "noisicaa/audioproc/public/processor_message.pb.h"
#include "noisicaa/audioproc/engine/message_queue.h"
#include "noisicaa/host_system/host_system.h"
#include "noisicaa/builtin_nodes/processor_message_registry.pb.h"
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
  _record_state_urid = _host_system->lv2->map(
      "http://noisicaa.odahoda.de/lv2/processor_midi_looper#record_state");
  _recorded_event_urid = _host_system->lv2->map(
      "http://noisicaa.odahoda.de/lv2/processor_midi_looper#recorded_event");
  lv2_atom_forge_init(&_node_msg_forge, &_host_system->lv2->urid_map);
  lv2_atom_forge_init(&_out_forge, &_host_system->lv2->urid_map);
}

Status ProcessorMidiLooper::setup_internal() {
  RETURN_IF_ERROR(Processor::setup_internal());

  _buffers.resize(_desc.ports_size());
  _next_record_state.store(UNSET);
  _record_state = OFF;
  _recorded_count = 0;
  _playback_pos = MusicalTime(-1, 1);
  _playback_index = 0;

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

Status ProcessorMidiLooper::handle_message_internal(pb::ProcessorMessage* msg) {
  unique_ptr<pb::ProcessorMessage> msg_ptr(msg);
  if (msg->HasExtension(pb::midi_looper_record)) {
    const pb::MidiLooperRecord& m = msg->GetExtension(pb::midi_looper_record);
    if (m.start()) {
      _next_record_state.store(WAITING);
    }

    return Status::Ok();
  }

  return Processor::handle_message_internal(msg_ptr.release());
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

  RecordState next_record_state = _next_record_state.exchange(UNSET);
  if (next_record_state != UNSET) {
    _record_state = next_record_state;
    post_record_state(ctxt);
  }

  MusicalDuration duration = MusicalDuration(spec->duration());

  LV2_Atom_Sequence* seq = (LV2_Atom_Sequence*)_buffers[0];
  if (seq->atom.type != _host_system->lv2->urid.atom_sequence) {
    return ERROR_STATUS(
        "Excepted sequence in port 'in', got %d.", seq->atom.type);
  }
  LV2_Atom_Event* event = lv2_atom_sequence_begin(&seq->body);

  LV2_Atom_Forge_Frame frame;
  lv2_atom_forge_set_buffer(&_out_forge, _buffers[1], 10240);

  lv2_atom_forge_sequence_head(&_out_forge, &frame, _host_system->lv2->urid.atom_frame_time);

  SampleTime* stime = ctxt->time_map.get();
  for (uint32_t pos = 0; pos < _host_system->block_size(); ++pos, ++stime) {
    if (stime->start_time.numerator() < 0) {
      while (!lv2_atom_sequence_is_end(&seq->body, seq->atom.size, event)
             && event->time.frames <= pos) {
        LV2_Atom& atom = event->body;
        if (atom.type == _host_system->lv2->urid.midi_event) {
          uint8_t* midi = (uint8_t*)LV2_ATOM_CONTENTS(LV2_Atom, &atom);
          post_note(ctxt, MusicalTime(0, 1), midi, false);
        } else {
          _logger->warning("Ignoring event %d in sequence.", atom.type);
        }

        event = lv2_atom_sequence_next(event);
      }

      continue;
    }

    MusicalTime sstart = stime->start_time % duration;
    MusicalTime send = stime->end_time % duration;
    if (send == MusicalTime(0, 1)) {
      send += duration;
    }

    if (sstart <= MusicalTime(0, 1) && MusicalTime(0, 1) < send) {
      if (_record_state == WAITING) {
        _record_state = RECORDING;
        _recorded_count = 0;
        post_record_state(ctxt);
      } else if (_record_state == RECORDING) {
        _record_state = OFF;
        _playback_pos = MusicalTime(-1, 1);
        _playback_index = 0;
        post_record_state(ctxt);
      }
    }

    while (!lv2_atom_sequence_is_end(&seq->body, seq->atom.size, event)
           && event->time.frames <= pos) {
      LV2_Atom& atom = event->body;
      if (atom.type == _host_system->lv2->urid.midi_event) {
        uint8_t* midi = (uint8_t*)LV2_ATOM_CONTENTS(LV2_Atom, &atom);
        bool recorded = false;

        if (_record_state == RECORDING && _recorded_count < _recorded_max_count) {
          RecordedEvent& revent = _recorded_events[_recorded_count];
          revent.time = sstart;
          memcpy(revent.midi, midi, 3);
          ++_recorded_count;
          recorded = true;
        }

        if (_record_state == RECORDING || _record_state == WAITING) {
          lv2_atom_forge_frame_time(&_out_forge, pos);
          lv2_atom_forge_atom(&_out_forge, 3, _host_system->lv2->urid.midi_event);
          lv2_atom_forge_write(&_out_forge, midi, 3);
        }

        post_note(ctxt, sstart, midi, recorded);
      } else {
        _logger->warning("Ignoring event %d in sequence.", atom.type);
      }

      event = lv2_atom_sequence_next(event);
    }

    if (_record_state == OFF && _recorded_count > 0) {
      if (send > sstart) {
        RETURN_IF_ERROR(process_sample(pos, sstart, send));
      } else if (send < sstart) {
        RETURN_IF_ERROR(process_sample(pos, sstart, MusicalTime(0, 1) + duration));
        RETURN_IF_ERROR(process_sample(pos, MusicalTime(0, 1), send));
      } else {
        return ERROR_STATUS(
            "Invalid sample times %lld/%lld %lld/%lld",
            sstart.numerator(), sstart.denominator(), send.numerator(), send.denominator());
      }
    }

    if (pos == 0) {
      uint8_t atom[100];
      lv2_atom_forge_set_buffer(&_node_msg_forge, atom, sizeof(atom));

      LV2_Atom_Forge_Frame frame;
      lv2_atom_forge_object(&_node_msg_forge, &frame, _host_system->lv2->urid.core_nodemsg, 0);
      lv2_atom_forge_key(&_node_msg_forge, _current_position_urid);
      LV2_Atom_Forge_Frame tframe;
      lv2_atom_forge_tuple(&_node_msg_forge, &tframe);
      lv2_atom_forge_int(&_node_msg_forge, sstart.numerator());
      lv2_atom_forge_int(&_node_msg_forge, sstart.denominator());
      lv2_atom_forge_pop(&_node_msg_forge, &tframe);
      lv2_atom_forge_pop(&_node_msg_forge, &frame);

      NodeMessage::push(ctxt->out_messages, _node_id, (LV2_Atom*)atom);
    }
  }

  lv2_atom_forge_pop(&_out_forge, &frame);

  return Status::Ok();
}

Status ProcessorMidiLooper::process_sample(uint32_t pos, const MusicalTime& sstart, const MusicalTime& send) {
  if (_playback_pos != sstart) {
    _playback_index = 0;
    while (_playback_index < _recorded_count && _recorded_events[_playback_index].time < sstart) {
      ++_playback_index;
    }
  }

  while (_playback_index < _recorded_count) {
    const RecordedEvent& revent = _recorded_events[_playback_index];
    if (revent.time < sstart || revent.time >= send) {
      break;
    }

    lv2_atom_forge_frame_time(&_out_forge, pos);
    lv2_atom_forge_atom(&_out_forge, 3, _host_system->lv2->urid.midi_event);
    lv2_atom_forge_write(&_out_forge, revent.midi, 3);
    ++_playback_index;
  }

  _playback_pos = send;

  return Status::Ok();
}

void ProcessorMidiLooper::post_record_state(BlockContext* ctxt) {
  uint8_t atom[100];
  lv2_atom_forge_set_buffer(&_node_msg_forge, atom, sizeof(atom));

  LV2_Atom_Forge_Frame frame;
  lv2_atom_forge_object(&_node_msg_forge, &frame, _host_system->lv2->urid.core_nodemsg, 0);
  lv2_atom_forge_key(&_node_msg_forge, _record_state_urid);
  lv2_atom_forge_int(&_node_msg_forge, _record_state);
  lv2_atom_forge_pop(&_node_msg_forge, &frame);

  NodeMessage::push(ctxt->out_messages, _node_id, (LV2_Atom*)atom);
}

void ProcessorMidiLooper::post_note(BlockContext* ctxt, const MusicalTime& time, uint8_t* midi, bool recorded) {
  uint8_t atom[100];
  lv2_atom_forge_set_buffer(&_node_msg_forge, atom, sizeof(atom));

  LV2_Atom_Forge_Frame frame;
  lv2_atom_forge_object(&_node_msg_forge, &frame, _host_system->lv2->urid.core_nodemsg, 0);
  lv2_atom_forge_key(&_node_msg_forge, _recorded_event_urid);
  LV2_Atom_Forge_Frame tframe;
  lv2_atom_forge_tuple(&_node_msg_forge, &tframe);
  lv2_atom_forge_int(&_node_msg_forge, time.numerator());
  lv2_atom_forge_int(&_node_msg_forge, time.denominator());
  lv2_atom_forge_atom(&_node_msg_forge, 3, _host_system->lv2->urid.midi_event);
  lv2_atom_forge_write(&_node_msg_forge, midi, 3);
  lv2_atom_forge_bool(&_node_msg_forge, recorded);
  lv2_atom_forge_pop(&_node_msg_forge, &tframe);
  lv2_atom_forge_pop(&_node_msg_forge, &frame);

  NodeMessage::push(ctxt->out_messages, _node_id, (LV2_Atom*)atom);
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
