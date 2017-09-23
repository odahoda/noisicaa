// -*- mode: c++ -*-

#ifndef _NOISICORE_PROCESSOR_LADSPA_H
#define _NOISICORE_PROCESSOR_LADSPA_H

#include <string>
#include <vector>
#include <stdint.h>
#include "ladspa.h"
#include "noisicaa/core/status.h"
#include "noisicore/buffers.h"
#include "noisicore/processor.h"

namespace noisicaa {

using namespace std;

class HostData;
class BlockContext;

class ProcessorLadspa : public Processor {
public:
  ProcessorLadspa(HostData* host_data);
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
