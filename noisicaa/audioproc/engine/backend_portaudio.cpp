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

#include "noisicaa/core/perf_stats.h"
#include "noisicaa/host_system/host_system.h"
#include "noisicaa/audioproc/engine/backend_portaudio.h"
#include "noisicaa/audioproc/engine/realm.h"

namespace noisicaa {

PortAudioBackend::PortAudioBackend(HostSystem* host_system, const BackendSettings& settings)
  : Backend(host_system, "noisicaa.audioproc.engine.backend.portaudio", settings),
    _initialized(false),
    _stream(nullptr),
    _samples{nullptr, nullptr} {
}

PortAudioBackend::~PortAudioBackend() {}

Status PortAudioBackend::setup(Realm* realm) {
  RETURN_IF_ERROR(Backend::setup(realm));

  PaError err = Pa_Initialize();
  if (err != paNoError) {
    return ERROR_STATUS("Failed to initialize portaudio: %s", Pa_GetErrorText(err));
  }
  _initialized = true;

  RETURN_IF_ERROR(setup_stream());

  return Status::Ok();
}

void PortAudioBackend::cleanup() {
  cleanup_stream();

  if (_initialized) {
    PaError err = Pa_Terminate();
    if (err != paNoError) {
      _logger->error("Failed to terminate portaudio: %s", Pa_GetErrorText(err));
    }
    _initialized = false;
  }

  Backend::cleanup();
}

Status PortAudioBackend::setup_stream() {
  assert(_stream == nullptr);

  PaDeviceIndex device_index = Pa_GetDefaultOutputDevice();
  const PaDeviceInfo* device_info = Pa_GetDeviceInfo(device_index);
  _logger->info("PortAudio device: %s", device_info->name);

  PaStreamParameters output_params;
  output_params.device = device_index;
  output_params.channelCount = 2;
  output_params.sampleFormat = paFloat32 | paNonInterleaved;
  output_params.suggestedLatency = device_info->defaultLowOutputLatency;
  output_params.hostApiSpecificStreamInfo = nullptr;

  PaError err;

  err = Pa_OpenStream(
      /* stream */            &_stream,
      /* inputParameters */   NULL,
      /* outputParameters */  &output_params,
      /* sampleRate */        _host_system->sample_rate(),
      /* framesPerBuffer */   _host_system->block_size(),
      /* streamFlags */       paNoFlag,
      /* streamCallback */    nullptr,
      /* userdata */          nullptr);
  if (err != paNoError) {
    return ERROR_STATUS("Failed to open portaudio stream: %s", Pa_GetErrorText(err));
  }

  err = Pa_StartStream(_stream);
  if (err != paNoError) {
    return ERROR_STATUS("Failed to start portaudio stream: %s", Pa_GetErrorText(err));
  }

  for (int c = 0 ; c < 2 ; ++c) {
    assert(_samples[c] == nullptr);
    _samples[c] = new uint8_t[_host_system->block_size() * sizeof(float)];
  }

  return Status::Ok();
}

void PortAudioBackend::cleanup_stream() {
  for (int c = 0 ; c < 2 ; ++c) {
    if (_samples[c] != nullptr) {
      delete _samples[c];
      _samples[c] = nullptr;
    }
  }

  if (_stream != nullptr) {
    PaError err = Pa_CloseStream(_stream);
    if (err != paNoError) {
      _logger->error("Failed to close portaudio stream: %s", Pa_GetErrorText(err));
    }
    _stream = nullptr;
  }
}

Status PortAudioBackend::begin_block(BlockContext* ctxt) {
  assert(ctxt->perf->current_span_id() == 0);
  ctxt->perf->start_span("frame");

  for (int c = 0 ; c < 2 ; ++c) {
    memset(_samples[c], 0, _host_system->block_size() * sizeof(float));
  }

  {
    lock_guard<mutex> lock(_msg_queue_mutex);
    ctxt->in_messages.clear();
    for (const auto& msg : _msg_queue) {
      ctxt->in_messages.emplace_back(msg);
    }
    _msg_queue.clear();
  }

  return Status::Ok();
}

Status PortAudioBackend::end_block(BlockContext* ctxt) {
  ctxt->perf->end_span();
  assert(ctxt->perf->current_span_id() == 0);

  PaError err = Pa_WriteStream(_stream, _samples, _host_system->block_size());
  if (err == paOutputUnderflowed) {
    _logger->warning("Buffer underrun.");
  } else if (err != paNoError) {
    return ERROR_STATUS("Failed to write to portaudio stream: %s", Pa_GetErrorText(err));
  }
  return Status::Ok();
}

Status PortAudioBackend::output(BlockContext* ctxt, const string& channel, BufferPtr samples) {
  if (channel == "left") {
    memmove(_samples[0], samples, _host_system->block_size() * sizeof(float));
  } else if (channel == "right") {
    memmove(_samples[1], samples, _host_system->block_size() * sizeof(float));
  } else {
    return ERROR_STATUS("Invalid channel %s", channel.c_str());
  }
  return Status::Ok();
}

}  // namespace noisicaa
