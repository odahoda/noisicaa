#include "vm.h"

#include <stdio.h>
#include <string.h>

#include "status.h"

namespace noisicaa {

Status Program::setup(const Spec* s) {
  spec.reset(s);

  for (int i = 0 ; i < spec->num_buffers() ; ++i) {
    unique_ptr<Buffer> buf(new Buffer(spec->get_buffer(i)));
    Status status = buf->allocate(spec->frame_size());
    if (status.is_error()) { return status; }
    buffers.emplace_back(buf.release());
  }

  return Status::Ok();
}

VM::VM() {
}

VM::~VM() {
}

Status VM::setup() {
  return Status::Ok();
}

Status VM::cleanup() {
  return Status::Ok();
}

Status VM::set_spec(const Spec* spec) {
  unique_ptr<Program> program(new Program);

  Status status = program->setup(spec);
  if (status.is_error()) { return status; }

  _program.reset(program.release());
  return Status::Ok();
}

Buffer* VM::get_buffer(const string& name) {
  if (_program.get() == nullptr) {
    return nullptr;
  }

  int idx = _program->spec->get_buffer_idx(name);
  return _program->buffers[idx].get();
}

Status VM::process_frame() {
  Program *program = _program.get();
  if (program == nullptr) {
    return Status::Ok();
  }

  const Spec* spec = program->spec.get();
  vector<unique_ptr<Buffer>>& buffers = program->buffers;

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
    case CLEAR: {
      int idx = spec->get_oparg(p, 0).int_value();
      Buffer* buf = buffers[idx].get();
      buf->clear();
      break;
    }
    case COPY: {
      int idx1 = spec->get_oparg(p, 0).int_value();
      int idx2 = spec->get_oparg(p, 1).int_value();
      Buffer* buf1 = buffers[idx1].get();
      Buffer* buf2 = buffers[idx2].get();
      // assert buf1->size() == buf2->size()
      memmove(buf2->data(), buf1->data(), buf2->size());
      break;
    }
    case MIX: {
      int idx1 = spec->get_oparg(p, 0).int_value();
      int idx2 = spec->get_oparg(p, 1).int_value();
      Buffer* buf1 = buffers[idx1].get();
      Buffer* buf2 = buffers[idx2].get();
      buf2->mix(buf1);
      break;
    }
    case FETCH_ENTITY: {
      const string& entity_id = spec->get_oparg(p, 0).string_value();
      int idx = spec->get_oparg(p, 1).int_value();
      printf("FETCH_ENTITY(%s, %d)\n", entity_id.c_str(), idx);
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
