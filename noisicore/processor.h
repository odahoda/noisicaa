#ifndef _NOISICORE_PROCESSOR_H
#define _NOISICORE_PROCESSOR_H

#include <memory>
#include <string>
#include <stdint.h>

#include "status.h"
#include "buffers.h"
#include "block_context.h"
#include "processor_spec.h"

namespace noisicaa {

using namespace std;

class HostData;

class Processor {
 public:
  Processor(HostData* host_data);
  virtual ~Processor();

  static Processor* create(HostData* host_data, const string& name);

  uint64_t id() const { return _id; }

  Status get_string_parameter(const string& name, string* value);

  virtual Status setup(const ProcessorSpec* spec);
  virtual void cleanup();

  virtual Status connect_port(uint32_t port_idx, BufferPtr buf) = 0;
  virtual Status run(BlockContext* ctxt) = 0;

 protected:
  HostData* _host_data;
  uint64_t _id;
  unique_ptr<const ProcessorSpec> _spec;

  static uint64_t new_id();
};

}  // namespace noisicaa

#endif
