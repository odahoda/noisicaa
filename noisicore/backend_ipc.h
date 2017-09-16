// -*- mode: c++ -*-

#ifndef _NOISICORE_BACKEND_IPC_H
#define _NOISICORE_BACKEND_IPC_H

#include <memory>
#include <string>
#include "noisicore/audio_stream.h"
#include "noisicore/backend.h"
#include "noisicore/buffers.h"
#include "noisicore/block_data.capnp.h"

namespace noisicaa {

class VM;

class IPCBackend : public Backend {
public:
  IPCBackend(const BackendSettings& settings);
  ~IPCBackend() override;

  Status setup(VM* vm) override;
  void cleanup() override;

  Status begin_block(BlockContext* ctxt) override;
  Status end_block(BlockContext* ctxt) override;
  Status output(BlockContext* ctxt, const string& channel, BufferPtr samples) override;

 private:
  unique_ptr<AudioStreamServer> _stream;
  capnp::BlockData::Builder _out_block = nullptr;
  uint32_t _block_size;
  unique_ptr<BufferData> _samples[2];
  bool _channel_written[2];
};

}  // namespace noisicaa

#endif
