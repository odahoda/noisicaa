// -*- mode: c++ -*-

#ifndef _NOISICORE_PROCESSOR_IPC_H
#define _NOISICORE_PROCESSOR_IPC_H

#include <string>
#include <vector>
#include <stdint.h>
#include "noisicaa/core/status.h"
#include "noisicore/buffers.h"
#include "noisicore/processor.h"
#include "noisicore/audio_stream.h"

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
