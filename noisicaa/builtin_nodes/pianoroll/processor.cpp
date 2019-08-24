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

#include <algorithm>

#include "noisicaa/core/perf_stats.h"
#include "noisicaa/audioproc/public/processor_message.pb.h"
#include "noisicaa/audioproc/engine/misc.h"
#include "noisicaa/host_system/host_system.h"
#include "noisicaa/audioproc/engine/double_buffered_state_manager.inl.h"
#include "noisicaa/builtin_nodes/processor_message_registry.pb.h"
#include "noisicaa/builtin_nodes/pianoroll/processor_messages.pb.h"
#include "noisicaa/builtin_nodes/pianoroll/processor.h"

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

  return sprintf("<event id=%016x time=%.2f type=%s pitch=%d velocity=%d>",
                 id, time.to_float(), type_str, pitch, velocity);
}

string PianoRollSegment::to_string() const {
  return sprintf("<segment id=%016x duration=%.2f>",
                 id, duration.to_float());
}

void PianoRollSegment::add_event(const PianoRollEvent& event) {
  auto it = lower_bound(events.begin(), events.end(), event, event_comp);
  events.insert(it, event);
}

void PianoRollSegment::remove_events(uint64_t id) {
  for (auto it = events.begin() ; it != events.end() ; ) {
    if (it->id == id) {
      it = events.erase(it);
    } else {
      ++it;
    }
  }
}

string PianoRollSegmentRef::to_string() const {
  return sprintf("<ref id=%016x time=%.2f segment=%016x>",
                 id, time.to_float(), segment->id);
}

PianoRoll::PianoRoll() {
  legacy_segment.reset(new PianoRollSegment());
}

void PianoRoll::apply_mutation(Logger* logger, pb::ProcessorMessage* msg) {
  if (msg->HasExtension(pb::pianoroll_add_interval)) {
    apply_add_interval(msg->GetExtension(pb::pianoroll_add_interval));
  } else if (msg->HasExtension(pb::pianoroll_remove_interval)) {
    apply_remove_interval(msg->GetExtension(pb::pianoroll_remove_interval));
  } else {
    assert(msg->HasExtension(pb::pianoroll_mutation));

    const pb::PianoRollMutation& mutation = msg->GetExtension(pb::pianoroll_mutation);
    switch (mutation.mutation_case()) {
    case pb::PianoRollMutation::kAddSegment:
      apply_add_segment(logger, mutation.add_segment());
      break;
    case pb::PianoRollMutation::kRemoveSegment:
      apply_remove_segment(logger, mutation.remove_segment());
      break;
    case pb::PianoRollMutation::kUpdateSegment:
      apply_update_segment(logger, mutation.update_segment());
      break;
    case pb::PianoRollMutation::kAddSegmentRef:
      apply_add_segment_ref(logger, mutation.add_segment_ref());
      break;
    case pb::PianoRollMutation::kRemoveSegmentRef:
      apply_remove_segment_ref(logger, mutation.remove_segment_ref());
      break;
    case pb::PianoRollMutation::kUpdateSegmentRef:
      apply_update_segment_ref(logger, mutation.update_segment_ref());
      break;
    case pb::PianoRollMutation::kAddEvent:
      apply_add_event(logger, mutation.add_event());
      break;
    case pb::PianoRollMutation::kRemoveEvent:
      apply_remove_event(logger, mutation.remove_event());
      break;
    case pb::PianoRollMutation::MUTATION_NOT_SET:
      logger->error("PianoRollMutation message without mutation.");
      break;
    }
  }

  // Invalidate pianoroll's cursor (so ProcessorPianoRoll::process_block() is forced to do a seek
  // first).
  current_ref = nullptr;
  offset = -1;
}

void PianoRoll::apply_add_interval(const pb::PianoRollAddInterval& msg) {
  PianoRollEvent event;
  event.id = msg.id();
  event.time = msg.start_time();
  event.type = PianoRollEvent::NOTE_ON;
  event.channel = 0;
  assert(msg.pitch() < 128);
  event.pitch = msg.pitch();
  assert(msg.velocity() < 128);
  event.velocity = msg.velocity();
  legacy_segment->add_event(event);

  event.id = msg.id();
  event.time = msg.end_time();
  event.type = PianoRollEvent::NOTE_OFF;
  event.channel = 0;
  assert(msg.pitch() < 128);
  event.pitch = msg.pitch();
  event.velocity = 0;
  legacy_segment->add_event(event);
}

void PianoRoll::apply_remove_interval(const pb::PianoRollRemoveInterval& msg) {
  legacy_segment->remove_events(msg.id());
}

void PianoRoll::apply_add_segment(Logger* logger, const pb::PianoRollMutation::AddSegment& msg) {
  assert(segment_map.count(msg.id()) == 0);
  PianoRollSegment* segment = new PianoRollSegment();
  segment->id = msg.id();
  segment->duration = msg.duration();
  segment_map[segment->id].reset(segment);
}

void PianoRoll::apply_remove_segment(Logger* logger, const pb::PianoRollMutation::RemoveSegment& msg) {
  assert(segment_map.count(msg.id()) > 0);
  segment_map.erase(msg.id());
}

void PianoRoll::apply_update_segment(Logger* logger, const pb::PianoRollMutation::UpdateSegment& msg) {
  assert(segment_map.count(msg.id()) > 0);
  PianoRollSegment* segment = segment_map[msg.id()].get();

  if (msg.has_duration()) {
    segment->duration = msg.duration();
  }
}

void PianoRoll::apply_add_segment_ref(Logger* logger, const pb::PianoRollMutation::AddSegmentRef& msg) {
  assert(ref_map.count(msg.id()) == 0);
  assert(segment_map.count(msg.segment_id()) > 0);

  PianoRollSegmentRef* ref = new PianoRollSegmentRef();
  ref->id = msg.id();
  ref->time = msg.time();
  ref->segment = segment_map[msg.segment_id()].get();
  ref_map[ref->id].reset(ref);
  refs.push_back(ref);
}

void PianoRoll::apply_remove_segment_ref(Logger* logger, const pb::PianoRollMutation::RemoveSegmentRef& msg) {
  assert(ref_map.count(msg.id()) > 0);
  for (auto it = refs.begin(); it < refs.end(); ++it) {
    if ((*it)->id == msg.id()) {
      refs.erase(it);
      break;
    }
  }
  ref_map.erase(msg.id());
}

void PianoRoll::apply_update_segment_ref(Logger* logger, const pb::PianoRollMutation::UpdateSegmentRef& msg) {
  assert(ref_map.count(msg.id()) > 0);
  PianoRollSegmentRef* segment_ref = ref_map[msg.id()].get();

  if (msg.has_time()) {
    segment_ref->time = msg.time();
  }
}

void PianoRoll::apply_add_event(Logger* logger, const pb::PianoRollMutation::AddEvent& msg) {
  assert(segment_map.count(msg.segment_id()) > 0);
  PianoRollSegment* segment = segment_map[msg.segment_id()].get();

  PianoRollEvent event;
  event.id = msg.id();
  event.time = msg.time();
  switch (msg.type()) {
  case pb::PianoRollMutation::AddEvent::NOTE_ON:
    event.type = PianoRollEvent::NOTE_ON;
    break;
  case pb::PianoRollMutation::AddEvent::NOTE_OFF:
    event.type = PianoRollEvent::NOTE_OFF;
    break;
  }
  assert(msg.channel() < 16);
  event.channel = msg.channel();
  assert(msg.pitch() < 128);
  event.pitch = msg.pitch();
  assert(msg.velocity() < 128);
  event.velocity = msg.velocity();
  segment->add_event(event);
}

void PianoRoll::apply_remove_event(Logger* logger, const pb::PianoRollMutation::RemoveEvent& msg) {
  assert(segment_map.count(msg.segment_id()) > 0);
  PianoRollSegment* segment = segment_map[msg.segment_id()].get();
  segment->remove_events(msg.id());
}

ProcessorPianoRoll::ProcessorPianoRoll(
    const string& realm_name, const string& node_id, HostSystem* host_system,
    const pb::NodeDescription& desc)
  : Processor(
      realm_name, node_id, "noisicaa.audioproc.engine.processor.pianoroll", host_system, desc),
    _pianoroll_manager(_logger) {}

ProcessorPianoRoll::~ProcessorPianoRoll() {}

Status ProcessorPianoRoll::setup_internal() {
  RETURN_IF_ERROR(Processor::setup_internal());

  for (int ch = 0 ; ch < 16 ; ++ch) {
    for (int p = 0 ; p < 128 ; ++p) {
      _active_notes[ch][p] = 0;
    }
  }

  return Status::Ok();
}

void ProcessorPianoRoll::cleanup_internal() {
  Processor::cleanup_internal();
}

Status ProcessorPianoRoll::handle_message_internal(pb::ProcessorMessage* msg) {
  if (msg->HasExtension(pb::pianoroll_add_interval)
      || msg->HasExtension(pb::pianoroll_remove_interval)
      || msg->HasExtension(pb::pianoroll_mutation)) {
    _pianoroll_manager.handle_mutation(msg);
    return Status::Ok();
  }

  return Processor::handle_message_internal(msg);
}

void ProcessorPianoRoll::note_on(
    LV2_Atom_Forge* forge, uint32_t sample, uint8_t channel, uint8_t pitch, uint8_t velocity) {
  assert(channel < 16);
  assert(pitch < 128);
  assert(velocity < 128);

  lv2_atom_forge_frame_time(forge, sample);
  lv2_atom_forge_atom(forge, 3, _host_system->lv2->urid.midi_event);
  uint8_t midi_data[3];
  midi_data[0] = 0x90 | channel;
  midi_data[1] = pitch;
  midi_data[2] = velocity;
  lv2_atom_forge_write(forge, midi_data, 3);
  _active_notes[channel][pitch] = 1;
}

void ProcessorPianoRoll::note_off(
    LV2_Atom_Forge* forge, uint32_t sample, uint8_t channel, uint8_t pitch) {
  assert(channel < 16);
  assert(pitch < 128);

  lv2_atom_forge_frame_time(forge, sample);
  lv2_atom_forge_atom(forge, 3, _host_system->lv2->urid.midi_event);
  uint8_t midi_data[3];
  midi_data[0] = 0x80 | channel;
  midi_data[1] = pitch;
  midi_data[2] = 0;
  lv2_atom_forge_write(forge, midi_data, 3);
  _active_notes[channel][pitch] = 0;
}

Status ProcessorPianoRoll::process_block_internal(BlockContext* ctxt, TimeMapper* time_mapper) {
  PerfTracker tracker(ctxt->perf.get(), "pianoroll");

  PianoRoll* pianoroll = _pianoroll_manager.get_current();

  memset(_buffers[0]->data(), 0, 10240);

  LV2_Atom_Forge forge;
  lv2_atom_forge_init(&forge, &_host_system->lv2->urid_map);

  LV2_Atom_Forge_Frame frame;
  lv2_atom_forge_set_buffer(&forge, _buffers[0]->data(), 10240);

  lv2_atom_forge_sequence_head(&forge, &frame, _host_system->lv2->urid.atom_frame_time);

  SampleTime* stime = ctxt->time_map.get();
  for (uint32_t sample = 0 ; sample < _host_system->block_size() ; ++sample, ++stime) {
    if (stime->start_time.numerator() < 0) {
      // playback turned off

      pianoroll->current_ref = nullptr;
      pianoroll->offset = -1;

      for (int ch = 0 ; ch < 16 ; ++ch) {
        for (int p = 0 ; p < 128 ; ++p) {
          if (_active_notes[ch][p]) {
            note_off(&forge, sample, ch, p);
          }
        }
      }

      continue;
    }

    PianoRollSegment* segment;
    MusicalTime segment_start_time;

    if (pianoroll->refs.size() > 0) {
      if (pianoroll->current_ref != nullptr && stime->start_time >= pianoroll->current_ref->time + pianoroll->current_ref->segment->duration) {
        pianoroll->current_ref = nullptr;
        pianoroll->offset = -1;
      }

      if (pianoroll->current_ref == nullptr || pianoroll->current_time != stime->start_time) {
        // Find segment at current time

        // TODO: do better than linear search.
        for (PianoRollSegmentRef* ref : pianoroll->refs) {
          if (stime->start_time >= ref->time
              && stime->start_time <= ref->time + ref->segment->duration) {
            pianoroll->current_ref = ref;
            break;
          }
        }
      }

      if (pianoroll->current_ref == nullptr) {
        // No segment at this point
        for (int ch = 0 ; ch < 16 ; ++ch) {
          for (int p = 0 ; p < 128 ; ++p) {
            if (_active_notes[ch][p]) {
              note_off(&forge, sample, ch, p);
            }
          }
        }
        continue;
      }

      segment = pianoroll->current_ref->segment;
      segment_start_time = pianoroll->current_ref->time;
    } else {
      segment = pianoroll->legacy_segment.get();
      segment_start_time = MusicalTime(0, 1);
    }

    // Current sample start/end time relative to segment
    MusicalTime start_time = stime->start_time - MusicalDuration(segment_start_time.numerator(), segment_start_time.denominator());
    MusicalTime end_time = stime->end_time - MusicalDuration(segment_start_time.numerator(), segment_start_time.denominator());

    if (pianoroll->offset < 0 || pianoroll->current_time != stime->start_time) {
      // Seek to new time.

      // TODO: We could to better than a sequential search.
      // - Do a binary search to find the new pianoroll->offset.
      // - Use an interval tree to find out which intervals are notes are active
      //   at that offset.

      uint8_t notes[16][128];
      for (int ch = 0 ; ch < 16 ; ++ch) {
        for (int p = 0 ; p < 128 ; ++p) {
          notes[ch][p] = 0;
        }
      }

      pianoroll->offset = 0;
      while ((size_t)pianoroll->offset < segment->events.size()) {
        const PianoRollEvent& event = segment->events[pianoroll->offset];

        if (event.time >= start_time) {
          break;
        }

        switch (event.type) {
        case PianoRollEvent::NOTE_ON:
          notes[event.channel][event.pitch] = 1;
          break;
        case PianoRollEvent::NOTE_OFF:
          notes[event.channel][event.pitch] = 0;
          break;
        }

        ++pianoroll->offset;
      }

      for (int ch = 0 ; ch < 16 ; ++ch) {
        for (int p = 0 ; p < 128 ; ++p) {
          if (_active_notes[ch][p] && !notes[ch][p]) {
            note_off(&forge, sample, ch, p);
          }
        }
      }
    }

    while ((size_t)pianoroll->offset < segment->events.size()) {
      const PianoRollEvent& event = segment->events[pianoroll->offset];
      assert(event.time >= start_time);
      if (event.time >= end_time) {
        // no more events at this sample.
        break;
      }

      switch (event.type) {
      case PianoRollEvent::NOTE_ON:
        note_on(&forge, sample, event.channel, event.pitch, event.velocity);
        break;
      case PianoRollEvent::NOTE_OFF:
        note_off(&forge, sample, event.channel, event.pitch);
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
