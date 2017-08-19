#include "backend.h"

#include <stdint.h>
#include <string.h>
#include "misc.h"
#include "portaudio.h"
#include "buffers.h"

namespace noisicaa {

Backend::Backend() {}

class PortAudioBackend : public Backend {
 public:
  PortAudioBackend()
    : _initialized(false),
      _stream(nullptr),
      _samples{nullptr, nullptr} {
  }

  ~PortAudioBackend() override {
  }

  Status setup() {
    uint32_t frame_size = 128;

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
	/* framesPerBuffer */   frame_size,
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
      _samples[c] = new uint8_t[frame_size * sizeof(float)];
    }

    return Status::Ok();
  }

  Status cleanup() {
    for (int c = 0 ; c < 2 ; ++c) {
      if (_samples[c] != nullptr) {
	delete _samples[c];
	_samples[c] = nullptr;
      }
    }

    if (_stream != nullptr) {
      PaError err = Pa_CloseStream(_stream);
      if (err != paNoError) {
	return Status::Error(
	    sprintf("Failed to close portaudio stream: %s", Pa_GetErrorText(err)));
      }
      _stream = nullptr;
    }

    if (_initialized) {
      PaError err = Pa_Terminate();
      if (err != paNoError) {
	return Status::Error(
	    sprintf("Failed to terminate portaudio: %s", Pa_GetErrorText(err)));
      }
      _initialized = false;
    }

    return Status::Ok();
  }

  Status begin_frame() {
    for (int c = 0 ; c < 2 ; ++c) {
      memset(_samples[c], 0, 128 * sizeof(float));
    }
    return Status::Ok();
  }

  Status end_frame() {
    PaError err = Pa_WriteStream(_stream, _samples, 128);
    if (err != paNoError) {
      return Status::Error(
	   sprintf("Failed to write to portaudio stream: %s", Pa_GetErrorText(err)));
    }
    return Status::Ok();
  }

  Status output(const string& channel, BufferPtr samples) {
    if (channel == "left") {
      memmove(_samples[0], samples, 128 * sizeof(float));
    } else if (channel == "right") {
      memmove(_samples[1], samples, 128 * sizeof(float));
    } else {
      return Status::Error(sprintf("Invalid channel %s", channel.c_str()));
    }
    return Status::Ok();
  }

 private:
  bool _initialized;
  PaStream* _stream;
  BufferPtr _samples[2];
};

Backend* Backend::create(const string& name) {
  if (name == "portaudio") {
    return new PortAudioBackend();
  } else {
    return nullptr;
  }
}

}  // namespace noisicaa
