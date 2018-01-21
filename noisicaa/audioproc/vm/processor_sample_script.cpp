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
#include "noisicaa/audioproc/public/time_mapper.h"
#include "noisicaa/audioproc/public/processor_message.pb.h"
#include "noisicaa/audioproc/vm/misc.h"
#include "noisicaa/audioproc/vm/host_data.h"
#include "noisicaa/audioproc/vm/double_buffered_state_manager.inl.h"
#include "noisicaa/audioproc/vm/vm.h"
#include "noisicaa/audioproc/vm/processor_sample_script.h"

namespace {

using namespace std;
using namespace noisicaa;

bool sample_comp(const Sample &e1, const Sample &e2) {
  return e1.time < e2.time;
}

}

namespace noisicaa {

SampleScript::SampleScript(Logger* logger, HostData* host_data)
  : _logger(logger),
    _host_data(host_data) {}

SampleScript::~SampleScript() {
  for (auto& sample : samples) {
    _host_data->audio_file->release_audio_file(sample.audio_file);
  }
}

void SampleScript::apply_mutation(pb::ProcessorMessage* msg) {
  switch (msg->msg_case()) {
  case pb::ProcessorMessage::kSampleScriptAddSample: {
    const pb::ProcessorMessage::SampleScriptAddSample& m = msg->sample_script_add_sample();

    StatusOr<AudioFile*> stor_audio_file =
      _host_data->audio_file->load_audio_file(m.sample_path());
    if (!stor_audio_file.is_error()) {
      Sample sample;
      sample.id = m.id();
      sample.time = m.time();
      sample.audio_file = stor_audio_file.result();
      _host_data->audio_file->acquire_audio_file(sample.audio_file);

      auto it = lower_bound(samples.begin(), samples.end(), sample, sample_comp);
      samples.insert(it, sample);
    } else {
      _logger->warning(
          "Failed to load audio file '%s': %s",
          m.sample_path().c_str(), stor_audio_file.message().c_str());
    }
    break;
  }

  case pb::ProcessorMessage::kSampleScriptRemoveSample: {
    const pb::ProcessorMessage::SampleScriptRemoveSample& m = msg->sample_script_remove_sample();

    for (auto it = samples.begin() ; it != samples.end() ; ) {
      if (it->id == m.id()) {
        _host_data->audio_file->release_audio_file(it->audio_file);
        it = samples.erase(it);
      } else {
        ++it;
      }
    }
    break;
  }

  default:
    assert(false);
  }

  // Invalidate script's cursor (so ProcessorSampleScript::run() is forced to do a seek first).
  offset = -1;
}

ProcessorSampleScript::ProcessorSampleScript(const string& node_id, HostData* host_data)
  : Processor(node_id, "noisicaa.audioproc.vm.processor.sample_script", host_data),
    _script_manager(
        new SampleScript(_logger, _host_data),
        new SampleScript(_logger, _host_data),
        _logger) {}

ProcessorSampleScript::~ProcessorSampleScript() {}

Status ProcessorSampleScript::setup(const ProcessorSpec* spec) {
  return Processor::setup(spec);
}

void ProcessorSampleScript::cleanup() {
  Processor::cleanup();
}

Status ProcessorSampleScript::handle_message_internal(pb::ProcessorMessage* msg) {
  switch (msg->msg_case()) {
  case pb::ProcessorMessage::kSampleScriptAddSample:
  case pb::ProcessorMessage::kSampleScriptRemoveSample:
    _script_manager.handle_mutation(msg);
    return Status::Ok();

  default:
    return Processor::handle_message_internal(msg);
  }
}

Status ProcessorSampleScript::connect_port(uint32_t port_idx, BufferPtr buf) {
  assert(port_idx < 2);
  _out_buffers[port_idx] = buf;
  return Status::Ok();
}

Status ProcessorSampleScript::run(BlockContext* ctxt, TimeMapper* time_mapper) {
  PerfTracker tracker(ctxt->perf.get(), "sample_script");

  SampleScript* script = _script_manager.get_current();

  assert(_out_buffers[0] != nullptr);
  float* out_l_ptr = (float*)_out_buffers[0];
  assert(_out_buffers[1] != nullptr);
  float* out_r_ptr = (float*)_out_buffers[1];

  for (uint32_t sample_pos = 0 ; sample_pos < ctxt->block_size ; ++sample_pos) {
    const SampleTime& stime = ctxt->time_map[sample_pos];

    if (stime.start_time.numerator() < 0) {
      // playback turned off
      script->offset = -1;
      *out_l_ptr++ = 0.0;
      *out_r_ptr++ = 0.0;
      continue;
    }

    float lvalue, rvalue;
    if (script->samples.size() == 0) {
      // No samples, always silence.
      lvalue = 0.0;
      rvalue = 0.0;
    } else {
      if (script->offset < 0 || script->current_time != stime.start_time) {
        // seek to new time.

        // TODO: We could to better than a sequential search.
        // - Do a binary search to find the new script->offset.

        script->offset = 0;
        while ((size_t)script->offset < script->samples.size()) {
          const Sample& sample = script->samples[script->offset];

          MusicalTime sample_end_time = time_mapper->sample_to_musical_time(
              time_mapper->musical_to_sample_time(sample.time)
              + sample.audio_file->num_samples());

          if (sample.time <= stime.start_time && sample_end_time >= stime.end_time) {
            // We seeked into an audio file.
            script->current_audio_file = sample.audio_file;
            script->file_offset = time_mapper->musical_to_sample_time(stime.start_time)
              - time_mapper->musical_to_sample_time(sample.time);
            ++script->offset;
            break;
          } else if (sample.time >= stime.start_time) {
            // We seeked into some empty space before an audio file.
            script->current_audio_file = nullptr;
            break;
          }

          ++script->offset;
        }
      }

      if ((size_t)script->offset < script->samples.size()) {
        const Sample& sample = script->samples[script->offset];
        assert(sample.time >= stime.start_time);
        if (sample.time < stime.end_time) {
          // Next audio file start playing.
          script->current_audio_file = sample.audio_file;
          script->file_offset = 0;
        }
      }

      if (script->current_audio_file == nullptr) {
        // No audio file playing, output silence.
        lvalue = 0.0;
        rvalue = 0.0;
      }
      else if (script->file_offset >= script->current_audio_file->num_samples()) {
        // End of audio file reached.
        script->current_audio_file = nullptr;
        lvalue = 0.0;
        rvalue = 0.0;
      } else {
        AudioFile* audio_file = script->current_audio_file;
        float values[2];
        for (int ch = 0 ; ch < 2 ; ++ch) {
          const float* channel_data = audio_file->channel_data(ch % audio_file->num_channels());
          values[ch] = channel_data[script->file_offset];
        }
        lvalue = values[0];
        rvalue = values[1];

        ++script->file_offset;
      }

      // Advance to next audio file, if needed. Might skip some audio files, if
      // they are so close together that they all fall into the same sample.
      while ((size_t)script->offset < script->samples.size()) {
        const Sample& sample = script->samples[script->offset];
        assert(sample.time >= stime.start_time);
        if (sample.time >= stime.end_time) {
          // no more audio files at this sample.
          break;
        }

        ++script->offset;
      }
    }

    *out_l_ptr++ = lvalue;
    *out_r_ptr++ = rvalue;

    script->current_time = stime.end_time;
  }

  return Status::Ok();
}

}
