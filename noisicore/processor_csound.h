// -*- mode: c++ -*-

#ifndef _NOISICORE_PROCESSOR_CSOUND_H
#define _NOISICORE_PROCESSOR_CSOUND_H

#include <atomic>
#include <string>
#include <vector>
#include <stdint.h>
#include "csound/csound.h"
#include "lv2/lv2plug.in/ns/ext/atom/forge.h"
#include "lv2/lv2plug.in/ns/ext/urid/urid.h"
#include "noisicore/status.h"
#include "noisicore/buffers.h"
#include "noisicore/processor.h"

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

  struct EventInputPort {
    LV2_Atom_Sequence* seq;
    LV2_Atom_Event* event;
    int instr;
  };

  vector<BufferPtr> _buffers;

  LV2_URID _sequence_urid;
  LV2_URID _midi_event_urid;
  vector<EventInputPort> _event_input_ports;

  atomic<Instance*> _next_instance;
  atomic<Instance*> _current_instance;
  atomic<Instance*> _old_instance;
};

class ProcessorCSound : public ProcessorCSoundBase {
public:
  ProcessorCSound(HostData* host_data);

  Status setup(const ProcessorSpec* spec) override;
  void cleanup() override;
};

class ProcessorCustomCSound : public ProcessorCSoundBase {
public:
  ProcessorCustomCSound(HostData* host_data);

  Status setup(const ProcessorSpec* spec) override;
  void cleanup() override;
};

}  // namespace noisicaa

#endif
