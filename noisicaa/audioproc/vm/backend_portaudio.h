// -*- mode: c++ -*-

#ifndef _NOISICAA_AUDIOPROC_VM_BACKEND_PORTAUDIO_H
#define _NOISICAA_AUDIOPROC_VM_BACKEND_PORTAUDIO_H

#include <string>
#include <stdint.h>
#include "portaudio.h"
#include "noisicaa/audioproc/vm/backend.h"
#include "noisicaa/audioproc/vm/buffers.h"

namespace noisicaa {

class VM;

class PortAudioBackend : public Backend {
public:
  PortAudioBackend(const BackendSettings& settings);
  ~PortAudioBackend() override;

  Status setup(VM* vm) override;
  void cleanup() override;

  Status set_block_size(uint32_t block_size) override;

  Status begin_block(BlockContext* ctxt) override;
  Status end_block(BlockContext* ctxt) override;
  Status output(BlockContext* ctxt, const string& channel, BufferPtr samples) override;

 private:
  bool _initialized;
  uint32_t _new_block_size;
  PaStream* _stream;
  BufferPtr _samples[2];
};

}  // namespace noisicaa

#endif
