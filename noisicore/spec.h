#ifndef _NOISICORE_SPEC_H
#define _NOISICORE_SPEC_H

#include <map>
#include <memory>
#include <vector>
#include <stdint.h>
#include "status.h"
#include "opcodes.h"
#include "buffers.h"

using std::map;
using std::unique_ptr;
using std::vector;

namespace noisicaa {

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

  Status set_frame_size(uint32_t frame_size);
  uint32_t frame_size() const { return _frame_size; }

  Status append_opcode(OpCode opcode, ...);
  int num_ops() const { return _opcodes.size(); }
  OpCode get_opcode(int idx) const { return _opcodes[idx].opcode; }
  const OpArg& get_oparg(int idx, int arg) const { return _opcodes[idx].args[arg]; }

  Status append_buffer(const string& name, BufferType* type);
  int num_buffers() const { return _buffers.size(); }
  const BufferType* get_buffer(int idx) const { return _buffers[idx].get(); }
  int get_buffer_idx(const string& name) const;

 private:
  uint32_t _frame_size;
  vector<Instruction> _opcodes;
  vector<unique_ptr<const BufferType>> _buffers;
  map<string, int> _buffer_map;
};

}  // namespace noisicaa

#endif
