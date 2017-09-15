// -*- mode: c++ -*-

#ifndef _NOISICORE_PROCESSOR_H
#define _NOISICORE_PROCESSOR_H

#include <map>
#include <memory>
#include <string>
#include <stdint.h>
#include "noisicore/status.h"
#include "noisicore/buffers.h"
#include "noisicore/block_context.h"
#include "noisicore/processor_spec.h"

namespace noisicaa {

using namespace std;

class HostData;

class Processor {
public:
  Processor(HostData* host_data);
  virtual ~Processor();

  static StatusOr<Processor*> create(HostData* host_data, const string& name);

  uint64_t id() const { return _id; }

  StatusOr<string> get_string_parameter(const string& name);
  Status set_string_parameter(const string& name, const string& value);

  StatusOr<int64_t> get_int_parameter(const string& name);
  Status set_int_parameter(const string& name, int64_t value);

  StatusOr<float> get_float_parameter(const string& name);
  Status set_float_parameter(const string& name, float value);

  virtual Status setup(const ProcessorSpec* spec);
  virtual void cleanup();

  virtual Status connect_port(uint32_t port_idx, BufferPtr buf) = 0;
  virtual Status run(BlockContext* ctxt) = 0;

protected:
  HostData* _host_data;
  uint64_t _id;
  unique_ptr<const ProcessorSpec> _spec;
  map<string, string> _string_parameters;
  map<string, int64_t> _int_parameters;
  map<string, float> _float_parameters;

  static uint64_t new_id();
};

}  // namespace noisicaa

#endif
