#include "spec.h"

#include <stdarg.h>

namespace noisicaa {

Spec::Spec() {
}

Spec::~Spec() {
}

Status Spec::append_opcode(OpCode opcode, ...) {
  vector<OpArg> args;

  struct OpSpec opspec = opspecs[opcode];

  va_list values;
  va_start(values, opcode);
  for (const char* a = opspec.argspec ; *a ; ++a) {
    switch (*a) {
    case 'i': {
      int64_t value = va_arg(values, int64_t);
      args.emplace_back(OpArg(value));
      break;
    }
    case 'f': {
      float value = va_arg(values, double);
      args.emplace_back(OpArg(value));
      break;
    }
    case 's': {
      const char* value = va_arg(values, char*);
      args.emplace_back(OpArg(value));
      break;
    }
    }
  }

  _opcodes.push_back({opcode, args});
  return Status::Ok();
}

}  // namespace noisicaa
