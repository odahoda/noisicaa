#ifndef _NOISICORE_PROCESSOR_CSOUND_H
#define _NOISICORE_PROCESSOR_CSOUND_H

#include <atomic>
#include <string>
#include <vector>
#include <stdint.h>
#include "csound/csound.h"

#include "status.h"
#include "buffers.h"
#include "processor.h"

using namespace std;

namespace noisicaa {

class HostData;
class BlockContext;

class ProcessorCSoundBase : public Processor {
 public:
  ProcessorCSoundBase(HostData* host_data);
  ~ProcessorCSoundBase() override;

  Status setup(const ProcessorSpec* spec) override;
  void cleanup() override;

  Status connect_port(uint32_t port_idx, BufferPtr buf) override;
  Status run(BlockContext* ctxt) override;

 protected:
  Status set_code(const string& orchestra, const string& score);

 private:
  vector<BufferPtr> _buffers;
  atomic<CSOUND*> _next_instance;
  atomic<CSOUND*> _current_instance;
  atomic<CSOUND*> _old_instance;
};

class ProcessorCSound : public ProcessorCSoundBase {
 public:
  ProcessorCSound(HostData* host_data);
  ~ProcessorCSound() override;

  Status setup(const ProcessorSpec* spec) override;
  void cleanup() override;
};

}  // namespace noisicaa

#endif
