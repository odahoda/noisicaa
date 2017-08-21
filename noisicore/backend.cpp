#include "backend.h"

#include <stdint.h>
#include <string.h>
#include "portaudio.h"

#include "misc.h"
#include "buffers.h"
#include "vm.h"

namespace noisicaa {

class PortAudioBackend : public Backend {
 public:
  PortAudioBackend()
    : _initialized(false),
      _block_size(128),
      _stream(nullptr),
      _samples{nullptr, nullptr} {
  }

  ~PortAudioBackend() override {
  }

  Status setup(VM* vm) override {
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

  void cleanup() override {
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
  }

  Status begin_block() override {
    for (int c = 0 ; c < 2 ; ++c) {
      memset(_samples[c], 0, _block_size * sizeof(float));
    }
    return Status::Ok();
  }

  Status end_block() override {
    PaError err = Pa_WriteStream(_stream, _samples, _block_size);
    if (err != paNoError) {
      return Status::Error(
	   sprintf("Failed to write to portaudio stream: %s", Pa_GetErrorText(err)));
    }
    return Status::Ok();
  }

  Status output(const string& channel, BufferPtr samples) override {
    if (channel == "left") {
      memmove(_samples[0], samples, _block_size * sizeof(float));
    } else if (channel == "right") {
      memmove(_samples[1], samples, _block_size * sizeof(float));
    } else {
      return Status::Error(sprintf("Invalid channel %s", channel.c_str()));
    }
    return Status::Ok();
  }

 private:
  bool _initialized;
  uint32_t _block_size;
  PaStream* _stream;
  BufferPtr _samples[2];
};

Backend::Backend() : _vm(nullptr) {}

Backend* Backend::create(const string& name) {
  if (name == "portaudio") {
    return new PortAudioBackend();
  } else {
    return nullptr;
  }
}

Status Backend::setup(VM* vm) {
  _vm = vm;
  return Status::Ok();
}

}  // namespace noisicaa
