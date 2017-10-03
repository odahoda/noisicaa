#include "noisicaa/core/perf_stats.h"
#include "noisicaa/audioproc/vm/backend_portaudio.h"
#include "noisicaa/audioproc/vm/vm.h"

namespace noisicaa {

PortAudioBackend::PortAudioBackend(const BackendSettings& settings)
  : Backend("noisicaa.audioproc.vm.backend.portaudio", settings),
    _initialized(false),
    _new_block_size(settings.block_size),
    _stream(nullptr),
    _samples{nullptr, nullptr} {
}

PortAudioBackend::~PortAudioBackend() {}

Status PortAudioBackend::setup(VM* vm) {
  Status status = Backend::setup(vm);
  if (status.is_error()) { return status; }

  if (_settings.block_size == 0) {
   return Status::Error("Invalid block_size %d", _settings.block_size);
  }

  PaError err;

  err = Pa_Initialize();
  if (err != paNoError) {
    return Status::Error("Failed to initialize portaudio: %s", Pa_GetErrorText(err));
  }
  _initialized = true;

  PaDeviceIndex device_index = Pa_GetDefaultOutputDevice();
  const PaDeviceInfo* device_info = Pa_GetDeviceInfo(device_index);
  _logger->info("PortAudio device: %s", device_info->name);

  PaStreamParameters output_params;
  output_params.device = device_index;
  output_params.channelCount = 2;
  output_params.sampleFormat = paFloat32 | paNonInterleaved;
  output_params.suggestedLatency = device_info->defaultLowOutputLatency;
  output_params.hostApiSpecificStreamInfo = nullptr;

  err = Pa_OpenStream(
      /* stream */            &_stream,
      /* inputParameters */   NULL,
      /* outputParameters */  &output_params,
      /* sampleRate */        44100,
      /* framesPerBuffer */   _settings.block_size,
      /* streamFlags */       paNoFlag,
      /* streamCallback */    nullptr,
      /* userdata */          nullptr);
  if (err != paNoError) {
    return Status::Error("Failed to open portaudio stream: %s", Pa_GetErrorText(err));
  }

  err = Pa_StartStream(_stream);
  if (err != paNoError) {
    return Status::Error("Failed to start portaudio stream: %s", Pa_GetErrorText(err));
  }

  for (int c = 0 ; c < 2 ; ++c) {
    _samples[c] = new uint8_t[_settings.block_size * sizeof(float)];
  }

  vm->set_block_size(_settings.block_size);

  return Status::Ok();
}

void PortAudioBackend::cleanup() {
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

  if (_initialized) {
    PaError err = Pa_Terminate();
    if (err != paNoError) {
      _logger->error("Failed to terminate portaudio: %s", Pa_GetErrorText(err));
    }
    _initialized = false;
  }

  Backend::cleanup();
}

Status PortAudioBackend::set_block_size(uint32_t block_size) {
  if (block_size == 0) {
   return Status::Error("Invalid block_size %d", block_size);
  }

  _new_block_size = block_size;
  return Status::Ok();
}

Status PortAudioBackend::begin_block(BlockContext* ctxt) {
  assert(ctxt->perf->current_span_id() == 0);
  ctxt->perf->start_span("frame");

  if (_new_block_size != _settings.block_size) {
    _settings.block_size = _new_block_size;

    for (int c = 0 ; c < 2 ; ++c) {
      if (_samples[c] != nullptr) {
	delete _samples[c];
      }
      _samples[c] = new uint8_t[_settings.block_size * sizeof(float)];
    }

    _vm->set_block_size(_settings.block_size);
  }

  for (int c = 0 ; c < 2 ; ++c) {
    memset(_samples[c], 0, _settings.block_size * sizeof(float));
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

  PaError err = Pa_WriteStream(_stream, _samples, _settings.block_size);
  if (err == paOutputUnderflowed) {
    _logger->warning("Buffer underrun.");
  } else if (err != paNoError) {
    return Status::Error("Failed to write to portaudio stream: %s", Pa_GetErrorText(err));
  }
  return Status::Ok();
}

Status PortAudioBackend::output(BlockContext* ctxt, const string& channel, BufferPtr samples) {
  if (channel == "left") {
    memmove(_samples[0], samples, _settings.block_size * sizeof(float));
  } else if (channel == "right") {
    memmove(_samples[1], samples, _settings.block_size * sizeof(float));
  } else {
    return Status::Error("Invalid channel %s", channel.c_str());
  }
  return Status::Ok();
}

}  // namespace noisicaa
