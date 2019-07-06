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
#include "noisicaa/builtin_nodes/midi_monitor/processor.h"

namespace noisicaa {

ProcessorMidiMonitor::ProcessorMidiMonitor(
    const string& realm_name, const string& node_id, HostSystem *host_system,
    const pb::NodeDescription& desc)
  : Processor(
      realm_name, node_id, "noisicaa.audioproc.engine.processor.midi_monitor", host_system, desc) {
  _midi_event_urid = _host_system->lv2->map(
      "http://noisicaa.odahoda.de/lv2/processor_midi_monitor#midi_event");
  lv2_atom_forge_init(&_node_msg_forge, &_host_system->lv2->urid_map);
}

Status ProcessorMidiMonitor::setup_internal() {
  return Processor::setup_internal();
}

void ProcessorMidiMonitor::cleanup_internal() {
  Processor::cleanup_internal();
}

Status ProcessorMidiMonitor::process_block_internal(BlockContext* ctxt, TimeMapper* time_mapper) {
  SampleTime* tmap = ctxt->time_map.get();

  LV2_Atom_Sequence* seq = (LV2_Atom_Sequence*)_buffers[0];
  if (seq->atom.type != _host_system->lv2->urid.atom_sequence) {
    return ERROR_STATUS(
        "Excepted sequence in port 'in', got %d.", seq->atom.type);
  }
  LV2_Atom_Event* event = lv2_atom_sequence_begin(&seq->body);
  while (!lv2_atom_sequence_is_end(&seq->body, seq->atom.size, event)) {
    assert(event->time.frames < _host_system->block_size());
    LV2_Atom& atom = event->body;
    if (atom.type == _host_system->lv2->urid.midi_event) {
      uint8_t* midi = (uint8_t*)LV2_ATOM_CONTENTS(LV2_Atom, &atom);
      post_event(ctxt, tmap[event->time.frames].start_time, midi);
    } else {
      _logger->warning("Ignoring event %d in sequence.", atom.type);
    }

    event = lv2_atom_sequence_next(event);
  }

  return Status::Ok();
}

void ProcessorMidiMonitor::post_event(BlockContext* ctxt, const MusicalTime& time, uint8_t* midi) {
  uint8_t atom[100];
  lv2_atom_forge_set_buffer(&_node_msg_forge, atom, sizeof(atom));

  LV2_Atom_Forge_Frame frame;
  lv2_atom_forge_object(&_node_msg_forge, &frame, _host_system->lv2->urid.core_nodemsg, 0);
  lv2_atom_forge_key(&_node_msg_forge, _midi_event_urid);
  LV2_Atom_Forge_Frame tframe;
  lv2_atom_forge_tuple(&_node_msg_forge, &tframe);
  lv2_atom_forge_int(&_node_msg_forge, time.numerator());
  lv2_atom_forge_int(&_node_msg_forge, time.denominator());
  lv2_atom_forge_atom(&_node_msg_forge, 3, _host_system->lv2->urid.midi_event);
  lv2_atom_forge_write(&_node_msg_forge, midi, 3);
  lv2_atom_forge_pop(&_node_msg_forge, &tframe);
  lv2_atom_forge_pop(&_node_msg_forge, &frame);

  NodeMessage::push(ctxt->out_messages, _node_id, (LV2_Atom*)atom);
}

}
