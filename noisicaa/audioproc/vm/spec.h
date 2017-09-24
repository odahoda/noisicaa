// -*- mode: c++ -*-

#ifndef _NOISICAA_AUDIOPROC_VM_SPEC_H
#define _NOISICAA_AUDIOPROC_VM_SPEC_H

#include <map>
#include <memory>
#include <vector>
#include <stdint.h>
#include "noisicaa/core/status.h"
#include "noisicaa/audioproc/vm/opcodes.h"

namespace noisicaa {

using namespace std;

class Processor;
class BufferType;

struct Instruction {
  OpCode opcode;
  vector<OpArg> args;
};

class Spec {
public:
  Spec();
  ~Spec();

  Spec(const Spec&) = delete;
  Spec operator=(const Spec&) = delete;

  Status append_opcode(OpCode opcode, ...);
  Status append_opcode_args(OpCode opcode, const vector<OpArg>& args);
  int num_ops() const { return _opcodes.size(); }
  const vector<OpArg> get_opargs(int idx) const { return _opcodes[idx].args; }
  OpCode get_opcode(int idx) const { return _opcodes[idx].opcode; }
  const OpArg& get_oparg(int idx, int arg) const { return _opcodes[idx].args[arg]; }

  Status append_buffer(const string& name, BufferType* type);
  int num_buffers() const { return _buffers.size(); }
  const BufferType* get_buffer(int idx) const { return _buffers[idx].get(); }
  StatusOr<int> get_buffer_idx(const string& name) const;

  Status append_processor(Processor* processor);
  int num_processors() const { return _processors.size(); }
  Processor* get_processor(int idx) const { return _processors[idx]; }
  StatusOr<int> get_processor_idx(const Processor* processor);

private:
  vector<Instruction> _opcodes;
  vector<Processor*> _processors;
  map<uint64_t, int> _processor_map;
  vector<unique_ptr<const BufferType>> _buffers;
  map<string, int> _buffer_map;
};

}  // namespace noisicaa

#endif
