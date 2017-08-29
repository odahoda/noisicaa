// -*- mode: c++ -*-

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

namespace noisicaa {

using namespace std;

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
  class Instance {
  public:
    Instance();
    ~Instance();

    Instance(const Instance&) = delete;
    Instance(Instance&&) = delete;
    Instance& operator=(const Instance&) = delete;
    Instance& operator=(Instance&&) = delete;

    CSOUND* csnd = nullptr;
    vector<MYFLT*> channel_ptr;
    vector<int*> channel_lock;
  };

  vector<BufferPtr> _buffers;
  atomic<Instance*> _next_instance;
  atomic<Instance*> _current_instance;
  atomic<Instance*> _old_instance;
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
