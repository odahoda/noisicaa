// -*- mode: c++ -*-

#ifndef _NOISICORE_BACKEND_IPC_H
#define _NOISICORE_BACKEND_IPC_H

#include <memory>
#include <string>
#include "audio_stream.h"
#include "backend.h"
#include "buffers.h"
#include "block_data.capnp.h"

namespace noisicaa {

class VM;

class IPCBackend : public Backend {
public:
  IPCBackend(const BackendSettings& settings);
  ~IPCBackend() override;

  Status setup(VM* vm) override;
  void cleanup() override;

  Status begin_block() override;
  Status end_block() override;
  Status output(const string& channel, BufferPtr samples) override;

 private:
  unique_ptr<AudioStreamServer> _stream;
  capnp::BlockData::Builder _out_block = nullptr;
  uint32_t _block_size = 128;
  unique_ptr<BufferData> _samples[2];
  bool _channel_written[2];
};

}  // namespace noisicaa

#endif
