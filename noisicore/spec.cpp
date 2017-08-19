#include "spec.h"

#include <stdarg.h>
#include "misc.h"

namespace noisicaa {

Spec::Spec()
  : _frame_size(128) {
}

Spec::~Spec() {
}

Status Spec::set_frame_size(uint32_t frame_size) {
  _frame_size = frame_size;
  return Status::Ok();
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
    case 'b': {
      const char* buf_name = va_arg(values, char*);
      int64_t value = get_buffer_idx(buf_name);
      if (value == -1) {
	return Status::Error(sprintf("Invalid buffer name %s", buf_name));
      }
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

Status Spec::append_buffer(const string& name, BufferType* type) {
  _buffer_map[name] = _buffers.size();
  _buffers.emplace_back(type);
  return Status::Ok();
}

int Spec::get_buffer_idx(const string& name) const {
  auto it = _buffer_map.find(name);
  if (it != _buffer_map.end()) {
    return it->second;
  }
  return -1;
}

}  // namespace noisicaa
