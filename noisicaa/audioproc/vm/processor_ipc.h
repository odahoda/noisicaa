// -*- mode: c++ -*-

#ifndef _NOISICAA_AUDIOPROC_VM_PROCESSOR_IPC_H
#define _NOISICAA_AUDIOPROC_VM_PROCESSOR_IPC_H

#include <string>
#include <vector>
#include <stdint.h>
#include "noisicaa/core/status.h"
#include "noisicaa/audioproc/vm/buffers.h"
#include "noisicaa/audioproc/vm/processor.h"
#include "noisicaa/audioproc/vm/audio_stream.h"

namespace noisicaa {

using namespace std;

class BlockContext;
class HostData;

class ProcessorIPC : public Processor {
public:
  ProcessorIPC(HostData* host_data);
  ~ProcessorIPC() override;

  Status setup(const ProcessorSpec* spec) override;
  void cleanup() override;

  Status connect_port(uint32_t port_idx, BufferPtr buf) override;
  Status run(BlockContext* ctxt) override;

private:
  BufferPtr _ports[2] = { nullptr, nullptr };
  unique_ptr<AudioStreamClient> _stream;
};

}  // namespace noisicaa

#endif
