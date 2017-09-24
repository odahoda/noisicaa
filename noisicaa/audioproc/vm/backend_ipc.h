// -*- mode: c++ -*-

#ifndef _NOISICAA_AUDIOPROC_VM_BACKEND_IPC_H
#define _NOISICAA_AUDIOPROC_VM_BACKEND_IPC_H

#include <memory>
#include <string>
#include "capnp/message.h"
#include "noisicaa/audioproc/vm/audio_stream.h"
#include "noisicaa/audioproc/vm/backend.h"
#include "noisicaa/audioproc/vm/buffers.h"
#include "noisicaa/audioproc/vm/block_data.capnp.h"

namespace noisicaa {

class IPCRequest;
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
  unique_ptr<IPCRequest> _request;
  unique_ptr<::capnp::MallocMessageBuilder> _message_builder;
  capnp::BlockData::Builder _out_block = nullptr;
  uint32_t _block_size;
  unique_ptr<BufferData> _samples[2];
  bool _channel_written[2];
};

}  // namespace noisicaa

#endif
