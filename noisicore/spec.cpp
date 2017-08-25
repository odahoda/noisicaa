#include "spec.h"

#include <stdarg.h>
#include "misc.h"
#include "processor.h"

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
    case 'b': {
      const char* buf_name = va_arg(values, char*);
      int64_t value = get_buffer_idx(buf_name);
      if (value == -1) {
	return Status::Error(sprintf("Invalid buffer name %s", buf_name));
      }
      args.emplace_back(OpArg(value));
      break;
    }
    case 'p': {
      Processor* processor = va_arg(values, Processor*);
      int64_t value = get_processor_idx(processor);
      if (value == -1) {
	return Status::Error(sprintf("Invalid processor %d", processor->id()));
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

Status Spec::append_processor(Processor* processor) {
  _processor_map[processor->id()] = _processors.size();
  _processors.push_back(processor);
  return Status::Ok();
}

int Spec::get_processor_idx(const Processor* processor) {
  auto it = _processor_map.find(processor->id());
  if (it != _processor_map.end()) {
    return it->second;
  }
  return -1;
}

}  // namespace noisicaa
