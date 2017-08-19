#include "vm.h"

#include <stdio.h>

#include "status.h"

namespace noisicaa {

VM::VM()
  : _current_spec(nullptr) {
}

VM::~VM() {
}

Status VM::setup() {
  return Status::Ok();
}

Status VM::cleanup() {
  return Status::Ok();
}

Status VM::set_spec(const Spec& spec) {
  _spec = spec;
  _current_spec = &_spec;
  return Status::Ok();
}

Status VM::process_frame() {
  const Spec *spec = _current_spec;
  if (spec == nullptr) {
    return Status::Ok();
  }

  int next_p = 0;
  while (true) {
    if (next_p == spec->num_ops()) {
      break;
    }

    int p = next_p;
    ++next_p;

    OpCode opcode = spec->get_opcode(p);
    bool end = false;
    switch (opcode) {
    case NOOP:
      break;
    case END:
      end = true;
      break;
    case COPY: {
      int buf1 = spec->get_oparg(p, 0).int_value();
      int buf2 = spec->get_oparg(p, 1).int_value();
      printf("COPY_BUFFER(%d, %d)\n", buf1, buf2);
      break;
    }
    case FETCH_ENTITY: {
      const string& entity_id = spec->get_oparg(p, 0).string_value();
      int buf = spec->get_oparg(p, 1).int_value();
      printf("FETCH_ENTITY(%s, %d)\n", entity_id.c_str(), buf);
      break;
    }
    default: {
      break;
    }
    }

    if (end) {
      break;
    }
  }
  return Status::Ok();
}

}  // namespace noisicaa
