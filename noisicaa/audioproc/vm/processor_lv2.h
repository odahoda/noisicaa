// -*- mode: c++ -*-

#ifndef _NOISICAA_AUDIOPROC_VM_PROCESSOR_LV2_H
#define _NOISICAA_AUDIOPROC_VM_PROCESSOR_LV2_H

#include <string>
#include <vector>
#include <stdint.h>
#include "lilv/lilv.h"
#include "noisicaa/core/status.h"
#include "noisicaa/audioproc/vm/buffers.h"
#include "noisicaa/audioproc/vm/processor.h"

namespace noisicaa {

using namespace std;

class BlockContext;
class HostData;

class ProcessorLV2 : public Processor {
public:
  ProcessorLV2(const string& node_id, HostData* host_data);
  ~ProcessorLV2() override;

  Status setup(const ProcessorSpec* spec) override;
  void cleanup() override;

  Status connect_port(uint32_t port_idx, BufferPtr buf) override;
  Status run(BlockContext* ctxt) override;

private:
  const LilvPlugin* _plugin = nullptr;
  LilvInstance* _instance = nullptr;
  LV2_Feature** _features = nullptr;
};

}  // namespace noisicaa

#endif
