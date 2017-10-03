#include <dlfcn.h>
#include <stdint.h>
#include <sndfile.h>
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

  // TODO: resample to VM's sample rate

  _left_samples.reset(new float[sfinfo.frames]);
  _right_samples.reset(new float[sfinfo.frames]);
  _loop = false;
  _playing = true;
  _pos = 0;
  _num_samples = sfinfo.frames;

  unique_ptr<float> frames(new float[1024 * sfinfo.channels]);
  sf_count_t pos = 0;
  while (pos < sfinfo.frames) {
    sf_count_t frames_read = sf_readf_float(fp, frames.get(), 1024);
    if (frames_read == 0) {
      return Status::Error("Failed to read all frames (%d != %d)", pos, sfinfo.frames);
    }

    float* lptr = _left_samples.get() + pos;
    float* rptr = _right_samples.get() + pos;
    float* in = frames.get();
    for (sf_count_t i = 0 ; i < frames_read ; ++i) {
      *lptr++ = *in;
      *rptr++ = *in;
      in += sfinfo.channels;
    }

    pos += frames_read;
  }

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
