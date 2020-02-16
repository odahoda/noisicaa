// -*- mode: c++ -*-

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

#ifndef _NOISICAA_HOST_SYSTEM_HOST_SYSTEM_AUDIO_FILE_H
#define _NOISICAA_HOST_SYSTEM_HOST_SYSTEM_AUDIO_FILE_H

#include <stdlib.h>
#include <map>
#include <memory>
#include <vector>
#include "noisicaa/core/status.h"

namespace noisicaa {

class Logger;

class AudioFile {
public:
  AudioFile(const string& path, uint32_t num_samples, float** channel_data);

  string path() const { return _path; }
  uint32_t num_samples() const { return _num_samples; }
  uint32_t num_channels() const { return _channel_data.size(); }
  const float* channel_data(uint32_t ch) const { return _channel_data[ch].get(); }

  uint32_t ref_count() const { return _ref_count; }
  void ref() { ++_ref_count; }
  void deref() { --_ref_count; }

private:
  string _path;
  uint32_t _ref_count = 0;
  uint32_t _num_samples;
  vector<unique_ptr<float>> _channel_data;
};

class AudioFileSubSystem {
public:
  AudioFileSubSystem();
  ~AudioFileSubSystem();

  Status setup(uint32_t sample_rate);
  void cleanup();

  StatusOr<AudioFile*> load_audio_file(const string& path);

  void acquire_audio_file(AudioFile* audio_file);
  void release_audio_file(AudioFile* audio_file);

private:
  Logger* _logger;
  uint32_t _sample_rate = 0;
  map<string, unique_ptr<AudioFile>> _map;
};

}  // namespace noisicaa

#endif
