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

#include "noisicaa/host_system/host_system.h"
#include "noisicaa/audioproc/public/processor_message.pb.h"
#include "noisicaa/audioproc/engine/misc.h"
#include "noisicaa/audioproc/engine/message_queue.h"
#include "noisicaa/builtin_nodes/vumeter/processor.h"

namespace noisicaa {

static const float min_db = -70.0f;
static const float max_db = 20.0f;

ProcessorVUMeter::ProcessorVUMeter(
    const string& realm_name, const string& node_id, HostSystem *host_system,
    const pb::NodeDescription& desc)
  : Processor(
      realm_name, node_id, "noisicaa.audioproc.engine.processor.vumeter", host_system, desc) {}

Status ProcessorVUMeter::setup_internal() {
  RETURN_IF_ERROR(Processor::setup_internal());

  _meter_urid = _host_system->lv2->map(
      "http://noisicaa.odahoda.de/lv2/processor_vumeter#meter");

  _window_size = min(
      (uint32_t)(0.05 * _host_system->sample_rate()),  // 50ms
      _host_system->sample_rate());
  _history_pos = 0;
  _peak_decay = 20 / (0.4 * _host_system->sample_rate());
  for (int ch = 0 ; ch < 2 ; ++ch) {
    _history[ch].reset(new float[_window_size]);
    for (uint32_t i = 0 ; i < _window_size ; ++i) {
      _history[ch].get()[i] = min_db;
    }

    _peak_hold[ch] = 0;
    _peak[ch] = min_db;
  }

  return Status::Ok();
}

void ProcessorVUMeter::cleanup_internal() {
  for (int ch = 0 ; ch < 2 ; ++ch) {
    _history[ch].reset();
  }

  Processor::cleanup_internal();
}

Status ProcessorVUMeter::process_block_internal(BlockContext* ctxt, TimeMapper* time_mapper) {
  static const int LEFT = 0;
  static const int RIGHT = 1;

  float* buf[2] = {
    (float*)_buffers[LEFT]->data(),
    (float*)_buffers[RIGHT]->data()
  };
  for (uint32_t i = 0 ; i < _host_system->block_size() ; ++i) {
    for (int ch = 0 ; ch < 2 ; ++ch) {
      float value = logf(fabsf(*(buf[ch]))) / 0.11512925f;
      value = max(min_db, min(value, max_db));

      _history[ch].get()[_history_pos] = value;

      if (value > _peak[ch]) {
        _peak_hold[ch] = int(0.5 * _host_system->sample_rate());
        _peak[ch] = value;
      } else if (_peak_hold[ch] == 0) {
        _peak[ch] = max(min_db, _peak[ch] - _peak_decay);
      } else {
        --_peak_hold[ch];
      }

      ++buf[ch];
    }

    _history_pos = (_history_pos + 1) % _window_size;
  }

  float current[2] = { min_db, min_db };
  for (uint32_t i = 0 ; i < _window_size ; ++i) {
    for (int ch = 0 ; ch < 2 ; ++ch) {
      current[ch] = max(current[ch], _history[ch].get()[i]);
    }
  }

  uint8_t atom[200];
  LV2_Atom_Forge forge;
  lv2_atom_forge_init(&forge, &_host_system->lv2->urid_map);
  lv2_atom_forge_set_buffer(&forge, atom, sizeof(atom));

  LV2_Atom_Forge_Frame oframe;
  lv2_atom_forge_object(&forge, &oframe, _host_system->lv2->urid.core_nodemsg, 0);

  lv2_atom_forge_key(&forge, _meter_urid);
  LV2_Atom_Forge_Frame tframe;
  lv2_atom_forge_tuple(&forge, &tframe);
  for (int ch = 0 ; ch < 2 ; ++ch) {
    lv2_atom_forge_float(&forge, current[ch]);
    lv2_atom_forge_float(&forge, _peak[ch]);
  }
  lv2_atom_forge_pop(&forge, &tframe);

  lv2_atom_forge_pop(&forge, &oframe);

  NodeMessage::push(ctxt->out_messages, _node_id, (LV2_Atom*)atom);

  return Status::Ok();
}

}
