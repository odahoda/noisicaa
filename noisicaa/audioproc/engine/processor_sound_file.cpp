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

#include <dlfcn.h>
#include <stdint.h>

#include "lv2/lv2plug.in/ns/ext/atom/forge.h"
#include "sndfile.h"
extern "C" {
#include "libswresample/swresample.h"
#include "libavutil/channel_layout.h"
}

#include "noisicaa/core/perf_stats.h"
#include "noisicaa/host_system/host_system.h"
#include "noisicaa/audioproc/engine/message_queue.h"
#include "noisicaa/audioproc/engine/misc.h"
#include "noisicaa/audioproc/engine/processor_sound_file.h"

namespace noisicaa {

ProcessorSoundFile::ProcessorSoundFile(
    const string& realm_name, const string& node_id, HostSystem* host_system,
    const pb::NodeDescription& desc)
  : Processor(
      realm_name, node_id, "noisicaa.audioproc.engine.processor.sound_file", host_system, desc) {}

ProcessorSoundFile::~ProcessorSoundFile() {}

Status ProcessorSoundFile::setup_internal() {
  RETURN_IF_ERROR(Processor::setup_internal());

  if (!_desc.has_sound_file()) {
    return ERROR_STATUS("NodeDescription misses sound_file field.");
  }

  _sound_file_complete_urid = _host_system->lv2->map(
      "http://noisicaa.odahoda.de/lv2/processor_sound_file#complete");

  StatusOr<AudioFile*> stor_audio_file = _host_system->audio_file->load_audio_file(
      _desc.sound_file().sound_file_path());
  RETURN_IF_ERROR(stor_audio_file);

  _audio_file = stor_audio_file.result();
  _host_system->audio_file->acquire_audio_file(_audio_file);
  _loop = false;
  _playing = true;
  _pos = 0;

  return Status::Ok();
}

void ProcessorSoundFile::cleanup_internal() {
  if (_audio_file != nullptr) {
    _host_system->audio_file->release_audio_file(_audio_file);
    _audio_file = nullptr;
  }

  Processor::cleanup_internal();
}

Status ProcessorSoundFile::process_block_internal(BlockContext* ctxt, TimeMapper* time_mapper) {
  PerfTracker tracker(ctxt->perf.get(), "sound_file");

  const float* l_in = _audio_file->channel_data(0);
  const float* r_in = _audio_file->channel_data(1 % _audio_file->num_channels());
  float* l_out = (float*)_buffers[0]->data();
  float* r_out = (float*)_buffers[1]->data();
  for (uint32_t i = 0 ; i < _host_system->block_size() ; ++i) {
    if (_pos >= _audio_file->num_samples()) {
      if (_loop) {
        _pos = 0;
      } else {
        if (_playing) {
          _playing = false;

          uint8_t buf[100];
          LV2_Atom_Forge forge;
          lv2_atom_forge_init(&forge, &_host_system->lv2->urid_map);

          lv2_atom_forge_set_buffer(&forge, buf, sizeof(buf));

          lv2_atom_forge_atom(&forge, 0, _sound_file_complete_urid);

          NodeMessage::push(ctxt->out_messages, node_id(), (LV2_Atom*)buf);
        }

        *l_out++ = 0.0;
        *r_out++ = 0.0;
        continue;
      }
    }

    *l_out++ = l_in[_pos];
    *r_out++ = r_in[_pos];

    _pos++;
  }

  return Status::Ok();
}

}
