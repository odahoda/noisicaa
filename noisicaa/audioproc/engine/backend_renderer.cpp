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

#include <fcntl.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <unistd.h>
#include <iostream>
extern "C" {
#include "libavutil/channel_layout.h"
}
#include "noisicaa/core/perf_stats.h"
#include "noisicaa/audioproc/engine/backend_renderer.h"
#include "noisicaa/host_system/host_system.h"
#include "noisicaa/audioproc/engine/realm.h"

namespace noisicaa {

RendererBackend::RendererBackend(
    HostSystem* host_system, const BackendSettings& settings,
    void (*callback)(void*, const string&), void *userdata)
  : Backend(
      host_system, "noisicaa.audioproc.engine.backend.renderer", settings, callback, userdata) {}

RendererBackend::~RendererBackend() {}

Status RendererBackend::setup(Realm* realm) {
  Status status = Backend::setup(realm);
  RETURN_IF_ERROR(status);

  if (_settings.datastream_address.size() == 0) {
    return ERROR_STATUS("datastream_address not set.");
  }

  _logger->info("Writing data stream to %s", _settings.datastream_address.c_str());
  _datastream = open(_settings.datastream_address.c_str(), O_RDWR);
  if (_datastream < 0) {
    return OSERROR_STATUS("Failed to open %s", _settings.datastream_address.c_str());
  }

  for (int c = 0 ; c < 2 ; ++c) {
    _samples[c].reset(new BufferData[_host_system->block_size() * sizeof(float)]);
  }

  _outbuf.reset(new float[2 * _host_system->block_size()]);

  return Status::Ok();
}

void RendererBackend::cleanup() {
  if (_datastream >= 0) {
    close(_datastream);
    _datastream = -1;
  }

  Backend::cleanup();
}

Status RendererBackend::begin_block(BlockContext* ctxt) {
  assert(ctxt->perf->current_span_id() == 0);
  ctxt->perf->start_span("frame");

  for (int c = 0 ; c < 2 ; ++c) {
    _channel_written[c] = false;
    memset(_samples[c].get(), 0, _host_system->block_size() * sizeof(float));
  }

  return Status::Ok();
}

Status RendererBackend::end_block(BlockContext* ctxt) {
  const float* left_in = (float*)_samples[0].get();
  const float* right_in = (float*)_samples[1].get();
  float* out = _outbuf.get();
  int num_samples = 0;
  SampleTime* stime = ctxt->time_map.get();
  SampleTime* stime_end = ctxt->time_map.get() + _host_system->block_size();
  while (stime < stime_end) {
    if (stime->start_time >= MusicalTime(0)) {
      *out++ = *left_in;
      *out++ = *right_in;
      ++num_samples;
    }

    ++left_in;
    ++right_in;
    ++stime;
  }

  if (num_samples > 0) {
    assert(_datastream >= 0);
    assert(num_samples <= (int)_host_system->block_size());

    size_t bytes_left = 2 * num_samples * sizeof(float);
    char* p = (char*)_outbuf.get();
    while (bytes_left > 0) {
      ssize_t bytes_written = write(_datastream, p, bytes_left);
      if (bytes_written < 0) {
        return OSERROR_STATUS("Failed to write to datastream");
      }

      bytes_left -= bytes_written;
      p += bytes_written;
    }

    _total_samples_written += num_samples;
  } else {
    if (_total_samples_written > 0 && _datastream >= 0) {
      // Signal the other end that we're done.
      _logger->info("Closing datastream.");
      ::close(_datastream);
      _datastream = -1;
    }
    // When we're not playing, sleep a bit, so we don't hog the CPU.
    usleep(10000);
  }

  ctxt->perf->end_span();
  assert(ctxt->perf->current_span_id() == 0);

  return Status::Ok();
}

Status RendererBackend::output(BlockContext* ctxt, Channel channel, BufferPtr buffer) {
  int c;
  switch (channel) {
  case AUDIO_LEFT:  c = 0; break;
  case AUDIO_RIGHT: c = 1; break;
  default: return ERROR_STATUS("Invalid channel %d", channel);
  }

  if (_channel_written[c]) {
    return ERROR_STATUS("Channel %d written multiple times.", c);
  }
  _channel_written[c] = true;
  memmove(_samples[c].get(), buffer, _host_system->block_size() * sizeof(float));

  return Status::Ok();
}

}  // namespace noisicaa
