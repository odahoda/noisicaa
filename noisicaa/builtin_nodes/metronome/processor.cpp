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
#include "noisicaa/builtin_nodes/processor_message_registry.pb.h"
#include "noisicaa/builtin_nodes/metronome/processor.h"
#include "noisicaa/builtin_nodes/metronome/processor.pb.h"

namespace noisicaa {

ProcessorMetronome::ProcessorMetronome(
    const string& realm_name, const string& node_id, HostSystem *host_system,
    const pb::NodeDescription& desc)
  : Processor(
      realm_name, node_id, "noisicaa.audioproc.engine.processor.metronome", host_system, desc),
    _next_spec(nullptr),
    _current_spec(nullptr),
    _old_spec(nullptr) {
  _tick_urid = _host_system->lv2->map(
      "http://noisicaa.odahoda.de/lv2/processor_metronome#tick");
  lv2_atom_forge_init(&_node_msg_forge, &_host_system->lv2->urid_map);
}

Status ProcessorMetronome::setup_internal() {
  RETURN_IF_ERROR(Processor::setup_internal());

  _pos = -1;

  return Status::Ok();
}

void ProcessorMetronome::cleanup_internal() {
  Spec* spec = _next_spec.exchange(nullptr);
  if (spec != nullptr) {
    _host_system->audio_file->release_audio_file(spec->audio_file);
    delete spec;
  }
  spec = _current_spec.exchange(nullptr);
  if (spec != nullptr) {
    _host_system->audio_file->release_audio_file(spec->audio_file);
    delete spec;
  }
  spec = _old_spec.exchange(nullptr);
  if (spec != nullptr) {
    _host_system->audio_file->release_audio_file(spec->audio_file);
    delete spec;
  }

  Processor::cleanup_internal();
}

Status ProcessorMetronome::set_parameters_internal(const pb::NodeParameters& parameters) {
  if (parameters.HasExtension(pb::metronome_spec)) {
    const auto& spec = parameters.GetExtension(pb::metronome_spec);

    Status status = set_spec(spec);
    if (status.is_error()) {
      _logger->warning("Failed to update spec: %s", status.message());
    }
  }

  return Processor::set_parameters_internal(parameters);
}

Status ProcessorMetronome::process_block_internal(BlockContext* ctxt, TimeMapper* time_mapper) {
  // If there is a next spec, make it the current. The current spec becomes the old spec, which will
  // eventually be destroyed in the main thread.  It must not happen that a next spec is available,
  // before an old one has been disposed of.
  Spec* spec = _next_spec.exchange(nullptr);
  if (spec != nullptr) {
    Spec* old_spec = _current_spec.exchange(spec);
    old_spec = _old_spec.exchange(old_spec);
    assert(old_spec == nullptr);
  }

  spec = _current_spec.load();
  if (spec == nullptr) {
    // No spec yet, just clear my output ports.
    clear_all_outputs();
    return Status::Ok();
  }

  const float* l_in = spec->audio_file->channel_data(0);
  const float* r_in = spec->audio_file->channel_data(1 % spec->audio_file->num_channels());
  float* l_out = (float*)_buffers[0];
  float* r_out = (float*)_buffers[1];

  SampleTime* stime = ctxt->time_map.get();
  for (uint32_t pos = 0; pos < _host_system->block_size(); ++pos, ++stime) {
    if (stime->start_time.numerator() < 0) {
      *l_out++ = 0.0;
      *r_out++ = 0.0;
      continue;
    }

    MusicalTime sstart = stime->start_time % spec->duration;
    MusicalTime send = stime->end_time % spec->duration;
    if (send == MusicalTime(0, 1)) {
      send += spec->duration;
    }

    if (sstart <= MusicalTime(0, 1) && MusicalTime(0, 1) < send) {
      _pos = 0;

      uint8_t atom[100];
      lv2_atom_forge_set_buffer(&_node_msg_forge, atom, sizeof(atom));

      LV2_Atom_Forge_Frame frame;
      lv2_atom_forge_object(&_node_msg_forge, &frame, _host_system->lv2->urid.core_nodemsg, 0);
      lv2_atom_forge_key(&_node_msg_forge, _tick_urid);
      lv2_atom_forge_int(&_node_msg_forge, 0);
      lv2_atom_forge_pop(&_node_msg_forge, &frame);

      NodeMessage::push(ctxt->out_messages, _node_id, (LV2_Atom*)atom);
    }

    if (_pos < 0 || (uint32_t)_pos >= spec->audio_file->num_samples()) {
      *l_out++ = 0.0;
      *r_out++ = 0.0;
      continue;
    }

    *l_out++ = l_in[_pos];
    *r_out++ = r_in[_pos];
    ++_pos;
  }

  return Status::Ok();
}

Status ProcessorMetronome::set_spec(const pb::MetronomeSpec& spec) {
  _logger->info("Setting spec:\n%s", spec.DebugString().c_str());

  // Discard any next spec, which hasn't been picked up by the audio thread.
  Spec* prev_next_spec = _next_spec.exchange(nullptr);
  if (prev_next_spec != nullptr) {
    _host_system->audio_file->release_audio_file(prev_next_spec->audio_file);
    delete prev_next_spec;
  }

  // Discard spec, which the audio thread doesn't use anymore.
  Spec* old_spec = _old_spec.exchange(nullptr);
  if (old_spec != nullptr) {
    _host_system->audio_file->release_audio_file(old_spec->audio_file);
    delete old_spec;
  }

  StatusOr<AudioFile*> stor_audio_file = _host_system->audio_file->load_audio_file(
      spec.sample_path());
  RETURN_IF_ERROR(stor_audio_file);

  _host_system->audio_file->acquire_audio_file(stor_audio_file.result());

  // Create the new spec. If you fail from here, ensure the audio file is released!
  unique_ptr<Spec> new_spec(new Spec());
  new_spec->audio_file = stor_audio_file.result();
  new_spec->duration = MusicalDuration(spec.duration());

  // Make the new spec the next one for the audio thread.
  prev_next_spec = _next_spec.exchange(new_spec.release());
  assert(prev_next_spec == nullptr);

  return Status::Ok();
}

}
