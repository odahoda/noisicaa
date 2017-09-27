// -*- mode: c++ -*-

#ifndef _NOISICAA_AUDIOPROC_VM_VM_H
#define _NOISICAA_AUDIOPROC_VM_VM_H

#include <atomic>
#include <memory>
#include <mutex>
#include <string>
#include <vector>
#include <stdint.h>
#include "noisicaa/core/logging.h"
#include "noisicaa/core/status.h"
#include "noisicaa/audioproc/vm/spec.h"
#include "noisicaa/audioproc/vm/processor.h"

namespace noisicaa {

using namespace std;

class Backend;
class BlockContext;
class HostData;

class Program {
public:
  Program(Logger* logger, uint32_t version);
  ~Program();

  Status setup(HostData* host_data, const Spec* spec, uint32_t block_size);

  uint32_t version = 0;
  bool initialized = false;
  unique_ptr<const Spec> spec;
  uint32_t block_size;
  vector<unique_ptr<Buffer>> buffers;

private:
  Logger* _logger;
};

struct ProgramState {
  Logger* logger;
  HostData* host_data;
  Program* program;
  Backend* backend;
  int p;
  bool end;
};

struct ActiveProcessor {
  ActiveProcessor(Processor* processor) : processor(processor), ref_count(0) {}

  unique_ptr<Processor> processor;
  int ref_count;
};

class ControlValue {
public:
  enum Type {
    Float,
    Int,
  };

  virtual ~ControlValue();

  Type type() const { return _type; }

protected:
  ControlValue(Type type);

private:
  Type _type;
};

class FloatControlValue : public ControlValue {
public:
  FloatControlValue(float value);

  float value() const { return _value; }
  void set_value(float value) { _value = value; }

private:
  float _value;
};

class IntControlValue : public ControlValue {
public:
  IntControlValue(int64_t value);

  int64_t value() const { return _value; }
  void set_value(int64_t value) { _value = value; }

private:
  int64_t _value;
};

class VM {
public:
  VM(HostData* host_data);
  ~VM();

  Status setup();
  void cleanup();

  Status add_processor(Processor* processor);

  Status set_block_size(uint32_t block_size);
  Status set_spec(const Spec* spec);
  Status set_backend(Backend* backend);
  Backend* backend() const { return _backend.get(); }

  Status set_float_control_value(const string& name, float value);
  StatusOr<float> get_float_control_value(const string& name);
  Status delete_control_value(const string& name);

  Status process_block(BlockContext* ctxt);

  Buffer* get_buffer(const string& name);

private:
  Logger* _logger;
  HostData* _host_data;
  atomic<uint32_t> _block_size;
  atomic<Program*> _next_program;
  atomic<Program*> _current_program;
  atomic<Program*> _old_program;
  uint32_t _program_version = 0;
  unique_ptr<Backend> _backend;
  map<uint64_t, unique_ptr<ActiveProcessor>> _processors;
  mutex _control_values_mutex;
  map<string, unique_ptr<ControlValue>> _control_values;
};

}  // namespace noisicaa

#endif
