// -*- mode: c++ -*-

#ifndef _NOISICORE_BACKEND_PORTAUDIO_H
#define _NOISICORE_BACKEND_PORTAUDIO_H

#include <string>
#include <stdint.h>
#include "portaudio.h"
#include "noisicore/backend.h"
#include "noisicore/buffers.h"

namespace noisicaa {

class VM;

class PortAudioBackend : public Backend {
public:
  PortAudioBackend(const BackendSettings& settings);
  ~PortAudioBackend() override;

  Status setup(VM* vm) override;
  void cleanup() override;

  Status begin_block(BlockContext* ctxt) override;
  Status end_block() override;
  Status output(const string& channel, BufferPtr samples) override;

 private:
  bool _initialized;
  uint32_t _block_size;
  PaStream* _stream;
  BufferPtr _samples[2];
};

}  // namespace noisicaa

#endif
