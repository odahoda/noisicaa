// -*- mode: c++ -*-

#ifndef _NOISICORE_PROCESSOR_LV2_H
#define _NOISICORE_PROCESSOR_LV2_H

#include <string>
#include <vector>
#include <stdint.h>
#include "lilv/lilv.h"
#include "noisicore/status.h"
#include "noisicore/buffers.h"
#include "noisicore/processor.h"

namespace noisicaa {

using namespace std;

class BlockContext;
class HostData;

class ProcessorLV2 : public Processor {
public:
  ProcessorLV2(HostData* host_data);
  ~ProcessorLV2() override;

  Status setup(const ProcessorSpec* spec) override;
  void cleanup() override;

  Status connect_port(uint32_t port_idx, BufferPtr buf) override;
  Status run(BlockContext* ctxt) override;

private:
  const LilvPlugin* _plugin = nullptr;
  LilvInstance* _instance = nullptr;
};

}  // namespace noisicaa

#endif
