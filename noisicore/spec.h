#ifndef _NOISICORE_SPEC_H
#define _NOISICORE_SPEC_H

#include <vector>
#include <stdint.h>
#include "status.h"
#include "opcodes.h"

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

  Status append_opcode(OpCode opcode, ...);

  int num_ops() const { return _opcodes.size(); }
  OpCode get_opcode(int idx) const { return _opcodes[idx].opcode; }
  const OpArg& get_oparg(int idx, int arg) const { return _opcodes[idx].args[arg]; }

 private:
  vector<Instruction> _opcodes;
};

}  // namespace noisicaa

#endif
