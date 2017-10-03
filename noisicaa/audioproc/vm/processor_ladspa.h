// -*- mode: c++ -*-

#ifndef _NOISICAA_AUDIOPROC_VM_PROCESSOR_LADSPA_H
#define _NOISICAA_AUDIOPROC_VM_PROCESSOR_LADSPA_H

#include <string>
#include <vector>
#include <stdint.h>
#include "ladspa.h"
#include "noisicaa/core/status.h"
#include "noisicaa/audioproc/vm/buffers.h"
#include "noisicaa/audioproc/vm/processor.h"

namespace noisicaa {

using namespace std;

class HostData;
class BlockContext;

class ProcessorLadspa : public Processor {
public:
  ProcessorLadspa(const string& node_id, HostData* host_data);
  ~ProcessorLadspa() override;

  Status setup(const ProcessorSpec* spec) override;
  void cleanup() override;

  Status connect_port(uint32_t port_idx, BufferPtr buf) override;
  Status run(BlockContext* ctxt) override;

private:
  void* _library = nullptr;
  const LADSPA_Descriptor*_descriptor = nullptr;
  LADSPA_Handle _instance = nullptr;
};

}  // namespace noisicaa

#endif
