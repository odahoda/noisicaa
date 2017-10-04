/*
 * @begin:license
 *
 * Copyright (c) 2015-2017, Benjamin Niemann <pink@odahoda.de>
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
#include "sndfile.h"
extern "C" {
#include "libswresample/swresample.h"
#include "libavutil/channel_layout.h"
}
#include "noisicaa/core/perf_stats.h"
#include "noisicaa/audioproc/vm/message_queue.h"
#include "noisicaa/audioproc/vm/misc.h"
#include "noisicaa/audioproc/vm/processor_sound_file.h"

namespace noisicaa {

ProcessorSoundFile::ProcessorSoundFile(const string& node_id, HostData* host_data)
  : Processor(node_id, "noisicaa.audioproc.vm.processor.sound_file", host_data) {}

ProcessorSoundFile::~ProcessorSoundFile() {}

Status ProcessorSoundFile::setup(const ProcessorSpec* spec) {
  Status status = Processor::setup(spec);
  if (status.is_error()) { return status; }

  StatusOr<string> stor_or_path = get_string_parameter("sound_file_path");
  if (stor_or_path.is_error()) { return stor_or_path; }
  string path = stor_or_path.result();

  SF_INFO sfinfo;
  sfinfo.format = 0;
  SNDFILE* fp = sf_open(path.c_str(), SFM_READ, &sfinfo);
  if (fp == nullptr) {
    return Status::Error("Failed to open file %s: %s", path.c_str(), sf_strerror(nullptr));
  }

  auto close_fp = scopeGuard([fp]() { sf_close(fp); });

  _logger->info("Opened file %s", path.c_str());
  _logger->info("frames: %d", sfinfo.frames);
  _logger->info("samplerate: %d", sfinfo.samplerate);
  _logger->info("channels: %d", sfinfo.channels);
  _logger->info("format: 0x%08x", sfinfo.format);
  _logger->info("sections: %d", sfinfo.sections);
  _logger->info("seekable: %d", sfinfo.seekable);

  _loop = false;
  _playing = true;
  _pos = 0;
  _num_samples = av_rescale_rnd(sfinfo.frames, 44100, sfinfo.samplerate, AV_ROUND_UP);
  _left_samples.reset(new float[_num_samples]);
  _right_samples.reset(new float[_num_samples]);

  SwrContext* ctxt = swr_alloc_set_opts(
      nullptr,
      AV_CH_LAYOUT_STEREO, AV_SAMPLE_FMT_FLTP, 44100,
      av_get_default_channel_layout(sfinfo.channels), AV_SAMPLE_FMT_FLT, sfinfo.samplerate,
      0, nullptr);
  if (ctxt == nullptr) {
    return Status::Error("Failed to allocate swr context.");
  }

  auto free_ctxt = scopeGuard([&ctxt]() { swr_free(&ctxt); });

  int rc = swr_init(ctxt);
  if (rc) {
    char buf[AV_ERROR_MAX_STRING_SIZE];
    return Status::Error(
	"Failed to init swr context: %s", av_make_error_string(buf, sizeof(buf), rc));
  }

  unique_ptr<float> frames(new float[1024 * sfinfo.channels]);
  sf_count_t in_pos = 0;
  uint32_t out_pos = 0;
  while (in_pos < sfinfo.frames) {
    sf_count_t frames_read = sf_readf_float(fp, frames.get(), 1024);
    if (frames_read == 0) {
      return Status::Error("Failed to read all frames (%d != %d)", in_pos, sfinfo.frames);
    }

    const uint8_t* in_planes[1] = {
      (const uint8_t*)frames.get()
    };
    uint8_t* out_planes[2] = {
      (uint8_t*)(_left_samples.get() + out_pos),
      (uint8_t*)(_right_samples.get() + out_pos)
    };
    int samples_written = swr_convert(
	ctxt,
	out_planes, _num_samples - out_pos,
	in_planes, frames_read);
    if (rc < 0) {
      char buf[AV_ERROR_MAX_STRING_SIZE];
      return Status::Error(
	  "Failed to convert samples: %s", av_make_error_string(buf, sizeof(buf), samples_written));
    }

    in_pos += frames_read;
    out_pos += samples_written;
  }

  // Flush out any samples that swr_convert might have buffered.
  uint8_t* out_planes[2] = {
    (uint8_t*)(_left_samples.get() + out_pos),
    (uint8_t*)(_right_samples.get() + out_pos)
  };
  int samples_written = swr_convert(
      ctxt,
      out_planes, _num_samples - out_pos,
      nullptr, 0);
  if (rc < 0) {
    char buf[AV_ERROR_MAX_STRING_SIZE];
    return Status::Error(
	"Failed to convert samples: %s", av_make_error_string(buf, sizeof(buf), samples_written));
  }

  out_pos += samples_written;

  // In case we have written less than we anticipated.
  _num_samples = out_pos;

  return Status::Ok();
}

void ProcessorSoundFile::cleanup() {
  _left_samples.reset();
  _right_samples.reset();

  Processor::cleanup();
}

Status ProcessorSoundFile::connect_port(uint32_t port_idx, BufferPtr buf) {
  if (port_idx > 1) {
    return Status::Error("Invalid port index %d", port_idx);
  }

  _buf[port_idx] = buf;
  return Status::Ok();
}

Status ProcessorSoundFile::run(BlockContext* ctxt) {
  PerfTracker tracker(ctxt->perf.get(), "sound_file");

  float* l_in = _left_samples.get();
  float* r_in = _right_samples.get();
  float* l_out = (float*)_buf[0];
  float* r_out = (float*)_buf[1];
  for (uint32_t i = 0 ; i < ctxt->block_size ; ++i) {
    if (_pos >= _num_samples) {
      if (_loop) {
	_pos = 0;
      } else {
	if (_playing) {
	  _playing = false;

	  SoundFileCompleteMessage msg(node_id());
	  ctxt->out_messages->push(&msg);
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
