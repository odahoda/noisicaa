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

#include "sndfile.h"
extern "C" {
#include "libswresample/swresample.h"
#include "libavutil/channel_layout.h"
}

#include "noisicaa/core/logging.h"
#include "noisicaa/core/scope_guard.h"
#include "noisicaa/host_system/host_system_audio_file.h"

namespace noisicaa {

AudioFile::AudioFile(const string& key, uint32_t num_samples, float** channel_data)
  : _key(key),
    _num_samples(num_samples) {
  for (float** cdat = channel_data ; *cdat != nullptr ; ++cdat) {
    _channel_data.emplace_back(*cdat);
  }
}

AudioFileSubSystem::AudioFileSubSystem()
  : _logger(LoggerRegistry::get_logger("noisicaa.host_system.audio_file")) {}

AudioFileSubSystem::~AudioFileSubSystem() {
  cleanup();
}

Status AudioFileSubSystem::setup(uint32_t sample_rate) {
  _sample_rate = sample_rate;
  return Status::Ok();
}

void AudioFileSubSystem::cleanup() {
  _map.clear();
}

StatusOr<AudioFile*> AudioFileSubSystem::load_audio_file(const string& path) {
  const auto& it = _map.find(path);
  if (it != _map.end()) {
    it->second->ref();
    return it->second.get();
  }

  _logger->info("Load audio file '%s'", path.c_str());

  SF_INFO sfinfo;
  sfinfo.format = 0;
  SNDFILE* fp = sf_open(path.c_str(), SFM_READ, &sfinfo);
  if (fp == nullptr) {
    return ERROR_STATUS("Failed to open file %s: %s", path.c_str(), sf_strerror(nullptr));
  }

  auto close_fp = scopeGuard([fp]() { sf_close(fp); });

  _logger->info("Opened file %s", path.c_str());
  _logger->info("frames: %d", sfinfo.frames);
  _logger->info("samplerate: %d", sfinfo.samplerate);
  _logger->info("channels: %d", sfinfo.channels);
  _logger->info("format: 0x%08x", sfinfo.format);
  _logger->info("sections: %d", sfinfo.sections);
  _logger->info("seekable: %d", sfinfo.seekable);

  uint32_t num_samples = av_rescale_rnd(sfinfo.frames, _sample_rate, sfinfo.samplerate, AV_ROUND_UP);
  vector<unique_ptr<float>> channel_data;
  for (int i = 0 ; i < sfinfo.channels ; ++i) {
    channel_data.emplace_back(new float[num_samples]);
  }

  SwrContext* ctxt = swr_alloc_set_opts(
      nullptr,
      av_get_default_channel_layout(sfinfo.channels), AV_SAMPLE_FMT_FLTP, _sample_rate,
      av_get_default_channel_layout(sfinfo.channels), AV_SAMPLE_FMT_FLT, sfinfo.samplerate,
      0, nullptr);
  if (ctxt == nullptr) {
    return ERROR_STATUS("Failed to allocate swr context.");
  }

  auto free_ctxt = scopeGuard([&ctxt]() { swr_free(&ctxt); });

  int rc = swr_init(ctxt);
  if (rc) {
    char buf[AV_ERROR_MAX_STRING_SIZE];
    return ERROR_STATUS(
        "Failed to init swr context: %s", av_make_error_string(buf, sizeof(buf), rc));
  }

  unique_ptr<float> frames(new float[1024 * sfinfo.channels]);
  sf_count_t in_pos = 0;
  uint32_t out_pos = 0;
  const uint8_t* in_planes[1] = { (const uint8_t*)frames.get() };
  uint8_t* out_planes[32];
  while (in_pos < sfinfo.frames) {
    sf_count_t frames_read = sf_readf_float(fp, frames.get(), 1024);
    if (frames_read == 0) {
      return ERROR_STATUS("Failed to read all frames (%d != %d)", in_pos, sfinfo.frames);
    }

    for (int i = 0 ; i < sfinfo.channels ; ++i) {
      out_planes[i] = (uint8_t*)(channel_data[i].get() + out_pos);
    }

    int samples_written = swr_convert(
        ctxt,
        out_planes, num_samples - out_pos,
        in_planes, frames_read);
    if (samples_written < 0) {
      char buf[AV_ERROR_MAX_STRING_SIZE];
      return ERROR_STATUS(
          "Failed to convert samples: %s", av_make_error_string(buf, sizeof(buf), samples_written));
    }

    in_pos += frames_read;
    out_pos += samples_written;
  }

  // Flush out any samples that swr_convert might have buffered.
  for (int i = 0 ; i < sfinfo.channels ; ++i) {
    out_planes[i] = (uint8_t*)(channel_data[i].get() + out_pos);
  }
  int samples_written = swr_convert(
      ctxt,
      out_planes, num_samples - out_pos,
      nullptr, 0);
  if (rc < 0) {
    char buf[AV_ERROR_MAX_STRING_SIZE];
    return ERROR_STATUS(
        "Failed to convert samples: %s", av_make_error_string(buf, sizeof(buf), samples_written));
  }

  out_pos += samples_written;

  // In case we have written less than we anticipated.
  num_samples = out_pos;

  unique_ptr<float*> cdat(new float*[channel_data.size() + 1]);
  for (uint32_t ch = 0 ; ch < channel_data.size() ; ++ch) {
    cdat.get()[ch] = channel_data[ch].release();
  }
  cdat.get()[channel_data.size()] = nullptr;

  AudioFile* audio_file = new AudioFile(path, num_samples, cdat.get());
  audio_file->ref();
  _map.emplace(path, unique_ptr<AudioFile>(audio_file));

  return audio_file;
}

StatusOr<AudioFile*> AudioFileSubSystem::load_raw_file(
    uint32_t sample_rate, uint32_t num_samples, const vector<string>& paths) {
  string key;
  key += sample_rate;
  key += ":";
  key += num_samples;
  for (const auto& p : paths) {
    key += ":" + p;
  }

  const auto& it = _map.find(key);
  if (it != _map.end()) {
    it->second->ref();
    return it->second.get();
  }

  uint32_t num_channels = paths.size();
  uint32_t scaled_num_samples = av_rescale_rnd(num_samples, _sample_rate, sample_rate, AV_ROUND_UP);
  vector<unique_ptr<float>> channel_data;
  for (int i = 0 ; i < num_channels ; ++i) {
    channel_data.emplace_back(new float[scaled_num_samples]);
  }

  SwrContext* ctxt = swr_alloc_set_opts(
      nullptr,
      av_get_default_channel_layout(1), AV_SAMPLE_FMT_FLT, _sample_rate,
      av_get_default_channel_layout(1), AV_SAMPLE_FMT_FLT, sample_rate,
      0, nullptr);
  if (ctxt == nullptr) {
    return ERROR_STATUS("Failed to allocate swr context.");
  }

  auto free_ctxt = scopeGuard([&ctxt]() { swr_free(&ctxt); });

  uint32_t ch = 0;
  for (const auto& path : paths) {
    int rc = swr_init(ctxt);
    if (rc) {
      char buf[AV_ERROR_MAX_STRING_SIZE];
      return ERROR_STATUS(
          "Failed to init swr context: %s", av_make_error_string(buf, sizeof(buf), rc));
    }

    FILE* fp = fopen(path.c_str(), "r");
    if (fp == nullptr) {
      return ERROR_STATUS("Failed to open file %s: %s", path.c_str(), strerror(errno));
    }

    auto close_fp = scopeGuard([fp]() { fclose(fp); });

    float samples[1024];
    sf_count_t in_pos = 0;
    uint32_t out_pos = 0;
    const uint8_t* in_planes[1] = { (const uint8_t*)samples };
    uint8_t* out_planes[1];
    while (in_pos < num_samples) {
      size_t samples_read = fread(samples, sizeof(float), 1024, fp);
      if (samples_read == 0) {
        return ERROR_STATUS("Failed to read all samples (%d != %d)", in_pos, num_samples);
      }

      out_planes[0] = (uint8_t*)(channel_data[ch].get() + out_pos);

      int samples_written = swr_convert(
          ctxt,
          out_planes, scaled_num_samples - out_pos,
          in_planes, samples_read);
      if (samples_written < 0) {
        char buf[AV_ERROR_MAX_STRING_SIZE];
        return ERROR_STATUS(
            "Failed to convert samples: %s", av_make_error_string(buf, sizeof(buf), samples_written));
      }

      in_pos += samples_read;
      out_pos += samples_written;
    }

    // Flush out any samples that swr_convert might have buffered.
    out_planes[0] = (uint8_t*)(channel_data[ch].get() + out_pos);
    int samples_written = swr_convert(
        ctxt,
        out_planes, scaled_num_samples - out_pos,
        nullptr, 0);
    if (rc < 0) {
      char buf[AV_ERROR_MAX_STRING_SIZE];
      return ERROR_STATUS(
          "Failed to convert samples: %s", av_make_error_string(buf, sizeof(buf), samples_written));
    }

    swr_close(ctxt);
  }

  unique_ptr<float*> cdat(new float*[channel_data.size() + 1]);
  for (uint32_t ch = 0 ; ch < channel_data.size() ; ++ch) {
    cdat.get()[ch] = channel_data[ch].release();
  }
  cdat.get()[channel_data.size()] = nullptr;

  AudioFile* audio_file = new AudioFile(key, scaled_num_samples, cdat.get());
  audio_file->ref();
  _map.emplace(key, unique_ptr<AudioFile>(audio_file));

  return audio_file;
}

void AudioFileSubSystem::acquire_audio_file(AudioFile* audio_file) {
  assert(_map.find(audio_file->key()) != _map.end());
  audio_file->ref();
}

void AudioFileSubSystem::release_audio_file(AudioFile* audio_file) {
  auto it = _map.find(audio_file->key());
  assert(it != _map.end());
  assert(audio_file->ref_count() > 0);
  audio_file->deref();

  if (audio_file->ref_count() == 0) {
    _logger->info("Unload audio file '%s'", audio_file->key().c_str());
    _map.erase(it);
  }
}

}  // namespace noisicaa
