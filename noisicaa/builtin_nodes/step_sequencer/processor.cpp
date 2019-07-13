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
#include "noisicaa/audioproc/public/engine_notification.pb.h"
#include "noisicaa/audioproc/engine/message_queue.h"
#include "noisicaa/host_system/host_system.h"
#include "noisicaa/builtin_nodes/step_sequencer/processor.h"
#include "noisicaa/builtin_nodes/step_sequencer/processor.pb.h"
#include "noisicaa/builtin_nodes/step_sequencer/model.pb.h"

namespace noisicaa {

ProcessorStepSequencer::ProcessorStepSequencer(
    const string& realm_name, const string& node_id, HostSystem *host_system,
    const pb::NodeDescription& desc)
  : Processor(
      realm_name, node_id, "noisicaa.audioproc.engine.processor.step_sequencer", host_system, desc),
    _next_spec(nullptr),
    _current_spec(nullptr),
    _old_spec(nullptr) {
  _current_step_urid = _host_system->lv2->map(
      "http://noisicaa.odahoda.de/lv2/processor_step_sequencer#current_step");
}

Status ProcessorStepSequencer::setup_internal() {
  RETURN_IF_ERROR(Processor::setup_internal());

  _current_step = -1;
  _current_step_d = 0.0;

  return Status::Ok();
}

void ProcessorStepSequencer::cleanup_internal() {
  pb::StepSequencerSpec* spec = _next_spec.exchange(nullptr);
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

Status ProcessorStepSequencer::set_parameters_internal(const pb::NodeParameters& parameters) {
  if (parameters.HasExtension(pb::step_sequencer_spec)) {
    const auto& spec = parameters.GetExtension(pb::step_sequencer_spec);

    Status status = set_spec(spec);
    if (status.is_error()) {
      _logger->warning("Failed to update spec: %s", status.message());
    }
  }

  return Processor::set_parameters_internal(parameters);
}

Status ProcessorStepSequencer::process_block_internal(BlockContext* ctxt, TimeMapper* time_mapper) {
  // If there is a next sequence, make it the current. The current sequence becomes
  // the old sequence, which will eventually be destroyed in the main thread.
  // It must not happen that a next sequence is available, before an old one has
  // been disposed of.
  pb::StepSequencerSpec* spec = _next_spec.exchange(nullptr);
  if (spec != nullptr) {
    pb::StepSequencerSpec* old_spec = _current_spec.exchange(spec);
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

  float* tempo_buf = (float*)_buffers[0]->data();

  for (uint32_t s = 0 ; s < _host_system->block_size() ; ++s) {
    float tempo = tempo_buf[s];

    if (spec->time_synched()) {
    }

    int32_t current_step = (int32_t)_current_step_d;
    if (current_step < 0) {
      current_step = 0;
    }
    if (current_step >= spec->num_steps()) {
      current_step = spec->num_steps() - 1;
    }

    uint32_t buffer_idx = 1;
    for (const auto& channel : spec->channels()) {
      BufferPtr out = _buffers[buffer_idx]->data();
      switch(channel.type()) {
      case pb::StepSequencerChannel::VALUE:
        ((float*)out)[s] = channel.step_value(current_step);
        break;
      case pb::StepSequencerChannel::GATE:
        ((float*)out)[s] = channel.step_enabled(current_step) ? 1.0 : 0.0;
        break;
      case pb::StepSequencerChannel::TRIGGER:
        if (channel.step_enabled(current_step) && current_step != _current_step) {
          ((float*)out)[s] = 1.0;
        } else {
          ((float*)out)[s] = 0.0;
        }
        break;
      }
      ++buffer_idx;
    }

    if (current_step != _current_step) {
      _current_step = current_step;

      uint8_t atom[10000];
      LV2_Atom_Forge forge;
      lv2_atom_forge_init(&forge, &_host_system->lv2->urid_map);
      lv2_atom_forge_set_buffer(&forge, atom, sizeof(atom));

      LV2_Atom_Forge_Frame frame;
      lv2_atom_forge_object(&forge, &frame, _host_system->lv2->urid.core_nodemsg, 0);
      lv2_atom_forge_key(&forge, _current_step_urid);
      lv2_atom_forge_int(&forge, _current_step);
      lv2_atom_forge_pop(&forge, &frame);

      NodeMessage::push(ctxt->out_messages, _node_id, (LV2_Atom*)atom);
    }

    if (!spec->time_synched()) {
      _current_step_d += (double)tempo / (double)_host_system->sample_rate();
      _current_step_d = fmod(_current_step_d, spec->num_steps());
    }
  }

  return Status::Ok();
}

Status ProcessorStepSequencer::set_spec(const pb::StepSequencerSpec& spec) {
  _logger->info("Setting spec:\n%s", spec.DebugString().c_str());

  // Discard any next sequence, which hasn't been picked up by the audio thread.
  pb::StepSequencerSpec* prev_next_spec = _next_spec.exchange(nullptr);
  if (prev_next_spec != nullptr) {
    delete prev_next_spec;
  }

  // Discard sequence, which the audio thread doesn't use anymore.
  pb::StepSequencerSpec* old_spec = _old_spec.exchange(nullptr);
  if (old_spec != nullptr) {
    delete old_spec;
  }

  // Create the new sequence.
  unique_ptr<pb::StepSequencerSpec> new_spec(new pb::StepSequencerSpec());
  new_spec->CopyFrom(spec);

  // Make the new sequence the next one for the audio thread.
  prev_next_spec = _next_spec.exchange(new_spec.release());
  assert(prev_next_spec == nullptr);

  return Status::Ok();
}

}
