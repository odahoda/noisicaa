#include "backend_portaudio.h"
#include "misc.h"
#include "vm.h"

namespace noisicaa {

PortAudioBackend::PortAudioBackend(const BackendSettings& settings)
  : Backend(settings),
    _initialized(false),
    _block_size(128),
    _stream(nullptr),
    _samples{nullptr, nullptr} {
}

PortAudioBackend::~PortAudioBackend() {}

Status PortAudioBackend::setup(VM* vm) {
  Status status = Backend::setup(vm);
  if (status.is_error()) { return status; }

  PaError err;

  err = Pa_Initialize();
  if (err != paNoError) {
    return Status::Error(
        sprintf("Failed to initialize portaudio: %s", Pa_GetErrorText(err)));
  }
  _initialized = true;

  err = Pa_OpenDefaultStream(
      /* stream */            &_stream,
      /* numInputChannels */  0,
      /* numOutputChannels */ 2,
      /* sampleFormat */      paFloat32 | paNonInterleaved,
      /* sampleRate */        44100,
      /* framesPerBuffer */   _block_size,
      /* streamCallback */    nullptr,
      /* userdata */          nullptr);
  if (err != paNoError) {
    return Status::Error(
	sprintf("Failed to open portaudio stream: %s", Pa_GetErrorText(err)));
  }

  err = Pa_StartStream(_stream);
  if (err != paNoError) {
    return Status::Error(
	sprintf("Failed to start portaudio stream: %s", Pa_GetErrorText(err)));
  }

  for (int c = 0 ; c < 2 ; ++c) {
    _samples[c] = new uint8_t[_block_size * sizeof(float)];
  }

  vm->set_block_size(_block_size);

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
      log(LogLevel::ERROR, "Failed to close portaudio stream: %s", Pa_GetErrorText(err));
    }
    _stream = nullptr;
  }

  if (_initialized) {
    PaError err = Pa_Terminate();
    if (err != paNoError) {
      log(LogLevel::ERROR, "Failed to terminate portaudio: %s", Pa_GetErrorText(err));
    }
    _initialized = false;
  }

  Backend::cleanup();
}

Status PortAudioBackend::begin_block() {
  for (int c = 0 ; c < 2 ; ++c) {
    memset(_samples[c], 0, _block_size * sizeof(float));
  }
  return Status::Ok();
}

Status PortAudioBackend::end_block() {
  PaError err = Pa_WriteStream(_stream, _samples, _block_size);
  if (err == paOutputUnderflowed) {
    log(LogLevel::WARNING, "Buffer underrun.");
  } else if (err != paNoError) {
    return Status::Error(
        sprintf("Failed to write to portaudio stream: %s", Pa_GetErrorText(err)));
  }
  return Status::Ok();
}

Status PortAudioBackend::output(const string& channel, BufferPtr samples) {
  if (channel == "left") {
    memmove(_samples[0], samples, _block_size * sizeof(float));
  } else if (channel == "right") {
    memmove(_samples[1], samples, _block_size * sizeof(float));
  } else {
    return Status::Error(sprintf("Invalid channel %s", channel.c_str()));
  }
  return Status::Ok();
}

}  // namespace noisicaa
