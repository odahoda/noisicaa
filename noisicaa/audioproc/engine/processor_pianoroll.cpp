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

#include <algorithm>

#include "noisicaa/core/perf_stats.h"
#include "noisicaa/audioproc/public/processor_message.pb.h"
#include "noisicaa/audioproc/engine/misc.h"
#include "noisicaa/host_system/host_system.h"
#include "noisicaa/audioproc/engine/double_buffered_state_manager.inl.h"
#include "noisicaa/audioproc/engine/processor_pianoroll.h"

namespace {

using namespace std;
using namespace noisicaa;

bool event_comp(const PianoRollEvent &e1, const PianoRollEvent &e2) {
  if (e1.time < e2.time) {
    return true;
  }

  if (e1.time == e2.time) {
    if (e1.type < e2.type) {
      return true;
    }

    if (e1.type == e2.type && e1.pitch < e2.pitch) {
      return true;
    }
  }

  return false;
}

}

namespace noisicaa {

string PianoRollEvent::to_string() const {
  const char* type_str = "??";
  switch (type) {
  case NOTE_ON:  type_str = "noteon";  break;
  case NOTE_OFF: type_str = "noteoff"; break;
  }

  return sprintf("<id=%016x time=%.2f type=%s pitch=%d velocity=%d>",
                 id, time.to_float(), type_str, pitch, velocity);
}

void PianoRoll::add_event(const PianoRollEvent& event) {
  auto it = lower_bound(events.begin(), events.end(), event, event_comp);
  events.insert(it, event);
}

void PianoRoll::remove_events(uint64_t id) {
  for (auto it = events.begin() ; it != events.end() ; ) {
    if (it->id == id) {
      it = events.erase(it);
    } else {
      ++it;
    }
  }
}

void PianoRoll::apply_mutation(pb::ProcessorMessage* msg) {
  switch (msg->msg_case()) {
  case pb::ProcessorMessage::kPianorollAddInterval:
    apply_add_interval(msg->pianoroll_add_interval());
    break;

  case pb::ProcessorMessage::kPianorollRemoveInterval:
    apply_remove_interval(msg->pianoroll_remove_interval());
    break;

  default:
    assert(false);
  }

  // Invalidate pianoroll's cursor (so ProcessorPianoRoll::process_block() is forced to do a seek
  // first).
  offset = -1;
}

void PianoRoll::apply_add_interval(const pb::ProcessorMessage::PianoRollAddInterval& msg) {
  PianoRollEvent event;
  event.id = msg.id();
  event.time = msg.start_time();
  event.type = PianoRollEvent::NOTE_ON;
  assert(msg.pitch() < 128);
  event.pitch = msg.pitch();
  assert(msg.velocity() < 128);
  event.velocity = msg.velocity();
  add_event(event);

  event.id = msg.id();
  event.time = msg.end_time();
  event.type = PianoRollEvent::NOTE_OFF;
  assert(msg.pitch() < 128);
  event.pitch = msg.pitch();
  event.velocity = 0;
  add_event(event);
}

void PianoRoll::apply_remove_interval(const pb::ProcessorMessage::PianoRollRemoveInterval& msg) {
  remove_events(msg.id());
}

ProcessorPianoRoll::ProcessorPianoRoll(
    const string& node_id, HostSystem* host_system, const pb::NodeDescription& desc)
  : Processor(node_id, "noisicaa.audioproc.engine.processor.pianoroll", host_system, desc),
    _pianoroll_manager(_logger) {}

ProcessorPianoRoll::~ProcessorPianoRoll() {}

Status ProcessorPianoRoll::setup_internal() {
  RETURN_IF_ERROR(Processor::setup_internal());

  for (int i = 0 ; i < 128 ; ++i) {
    _active_notes[i] = 0;
  }

  return Status::Ok();
}

void ProcessorPianoRoll::cleanup_internal() {
  Processor::cleanup_internal();
}

Status ProcessorPianoRoll::handle_message_internal(pb::ProcessorMessage* msg) {
  switch (msg->msg_case()) {
  case pb::ProcessorMessage::kPianorollAddInterval:
  case pb::ProcessorMessage::kPianorollRemoveInterval:
    _pianoroll_manager.handle_mutation(msg);
    return Status::Ok();

  default:
    return Processor::handle_message_internal(msg);
  }
}

Status ProcessorPianoRoll::connect_port_internal(
    BlockContext* ctxt, uint32_t port_idx, BufferPtr buf) {
  assert(port_idx == 0);
  _out_buffer = buf;
  return Status::Ok();
}

void ProcessorPianoRoll::note_on(
    LV2_Atom_Forge* forge, uint32_t sample, uint8_t pitch, uint8_t velocity) {
  lv2_atom_forge_frame_time(forge, sample);
  lv2_atom_forge_atom(forge, 3, _host_system->lv2->urid.midi_event);
  uint8_t midi_data[3] = { 0x90, pitch, velocity };
  lv2_atom_forge_write(forge, midi_data, 3);
  _active_notes[pitch] = 1;
}

void ProcessorPianoRoll::note_off(LV2_Atom_Forge* forge, uint32_t sample, uint8_t pitch) {
  lv2_atom_forge_frame_time(forge, sample);
  lv2_atom_forge_atom(forge, 3, _host_system->lv2->urid.midi_event);
  uint8_t midi_data[3] = { 0x80, pitch, 0 };
  lv2_atom_forge_write(forge, midi_data, 3);
  _active_notes[pitch] = 0;
}

Status ProcessorPianoRoll::process_block_internal(BlockContext* ctxt, TimeMapper* time_mapper) {
  PerfTracker tracker(ctxt->perf.get(), "pianoroll");

  PianoRoll* pianoroll = _pianoroll_manager.get_current();

  assert(_out_buffer != nullptr);
  memset(_out_buffer, 0, 10240);

  LV2_Atom_Forge forge;
  lv2_atom_forge_init(&forge, &_host_system->lv2->urid_map);

  LV2_Atom_Forge_Frame frame;
  lv2_atom_forge_set_buffer(&forge, _out_buffer, 10240);

  lv2_atom_forge_sequence_head(&forge, &frame, _host_system->lv2->urid.atom_frame_time);

  SampleTime* stime = ctxt->time_map.get();
  for (uint32_t sample = 0 ; sample < _host_system->block_size() ; ++sample, ++stime) {
    if (stime->start_time.numerator() < 0) {
      // playback turned off

      pianoroll->offset = -1;

      for (int i = 0 ; i < 128 ; ++i) {
        if (_active_notes[i]) {
          note_off(&forge, sample, i);
        }
      }

      continue;
    }

    if (pianoroll->offset < 0 || pianoroll->current_time != stime->start_time) {
      // Seek to new time.

      // TODO: We could to better than a sequential search.
      // - Do a binary search to find the new pianoroll->offset.
      // - Use an interval tree to find out which intervals are notes are active
      //   at that offset.

      uint8_t notes[128];
      for (int i = 0 ; i < 128 ; ++i) {
        notes[i] = 0;
      }

      pianoroll->offset = 0;
      while ((size_t)pianoroll->offset < pianoroll->events.size()) {
        const PianoRollEvent& event = pianoroll->events[pianoroll->offset];

        if (event.time >= stime->start_time) {
          break;
        }

        if (event.type == PianoRollEvent::NOTE_ON) {
          notes[event.pitch] = 1;
        } else if (event.type == PianoRollEvent::NOTE_OFF) {
          notes[event.pitch] = 0;
        }

        ++pianoroll->offset;
      }

      for (int i = 0 ; i < 128 ; ++i) {
        if (_active_notes[i] && !notes[i]) {
          note_off(&forge, sample, i);
        }
      }
    }

    while ((size_t)pianoroll->offset < pianoroll->events.size()) {
      const PianoRollEvent& event = pianoroll->events[pianoroll->offset];
      assert(event.time >= stime->start_time);
      if (event.time >= stime->end_time) {
        // no more events at this sample.
        break;
      }

      switch (event.type) {
      case PianoRollEvent::NOTE_ON:
        note_on(&forge, sample, event.pitch, event.velocity);
        break;
      case PianoRollEvent::NOTE_OFF:
        note_off(&forge, sample, event.pitch);
        break;
      }

      ++pianoroll->offset;
    }

    pianoroll->current_time = stime->end_time;
  }

  lv2_atom_forge_pop(&forge, &frame);

  return Status::Ok();
}

}
