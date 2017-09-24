// -*- mode: c++ -*-

#ifndef _NOISICAA_AUDIOPROC_VM_PROCESSOR_CSOUND_BASE_H
#define _NOISICAA_AUDIOPROC_VM_PROCESSOR_CSOUND_BASE_H

#include <atomic>
#include <string>
#include <vector>
#include <stdint.h>
#include "csound/csound.h"
#include "lv2/lv2plug.in/ns/ext/atom/forge.h"
#include "lv2/lv2plug.in/ns/ext/urid/urid.h"
#include "noisicaa/core/status.h"
#include "noisicaa/audioproc/vm/buffers.h"
#include "noisicaa/audioproc/vm/processor.h"

namespace noisicaa {

using namespace std;

class HostData;
class BlockContext;

class ProcessorCSoundBase : public Processor {
public:
  ProcessorCSoundBase(const char* logger_name, HostData* host_data);
  ~ProcessorCSoundBase() override;

  Status setup(const ProcessorSpec* spec) override;
  void cleanup() override;

  Status connect_port(uint32_t port_idx, BufferPtr buf) override;
  Status run(BlockContext* ctxt) override;

protected:
  Status set_code(const string& orchestra, const string& score);

private:
  static void _log_cb(CSOUND* csnd, int attr, const char* fmt, va_list args);
  void _log_cb(int attr, const char* fmt, va_list args);
  char _log_buf[10240];

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
  vector<EventInputPort> _event_input_ports;

  atomic<Instance*> _next_instance;
  atomic<Instance*> _current_instance;
  atomic<Instance*> _old_instance;
};

}  // namespace noisicaa

#endif
