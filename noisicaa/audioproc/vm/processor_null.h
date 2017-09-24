// -*- mode: c++ -*-

#ifndef _NOISICAA_AUDIOPROC_VM_PROCESSOR_NULL_H
#define _NOISICAA_AUDIOPROC_VM_PROCESSOR_NULL_H

#include <stdint.h>
#include "noisicaa/core/status.h"
#include "noisicaa/audioproc/vm/buffers.h"
#include "noisicaa/audioproc/vm/processor.h"

namespace noisicaa {

class BlockContext;
class HostData;

class ProcessorNull : public Processor {
public:
  ProcessorNull(HostData* host_data);
  ~ProcessorNull() override;

  Status setup(const ProcessorSpec* spec) override;
  void cleanup() override;

  Status connect_port(uint32_t port_idx, BufferPtr buf) override;
  Status run(BlockContext* ctxt) override;
};

}  // namespace noisicaa

#endif
