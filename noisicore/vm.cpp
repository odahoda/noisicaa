#include "vm.h"

#include <stdio.h>
#include <string.h>

#include "status.h"
#include "misc.h"

using std::atomic;

namespace noisicaa {

Status Program::setup(const Spec* s, uint32_t block_size) {
  spec.reset(s);
  this->block_size = block_size;

  for (int i = 0 ; i < spec->num_buffers() ; ++i) {
    unique_ptr<Buffer> buf(new Buffer(spec->get_buffer(i)));
    Status status = buf->allocate(block_size);
    if (status.is_error()) { return status; }
    buffers.emplace_back(buf.release());
  }

  return Status::Ok();
}

VM::VM() : _block_size(256) {
}

VM::~VM() {
}

Status VM::setup() {
  return Status::Ok();
}

void VM::cleanup() {
}

Status VM::set_block_size(uint32_t block_size) {
  _block_size.store(block_size);
  return Status::Ok();
}

Status VM::set_spec(const Spec* spec) {
  unique_ptr<Program> program(new Program);

  Status status = program->setup(spec, _block_size);
  if (status.is_error()) { return status; }

  // TODO: lockfree program life cycle:
  // 3 ptrs: new, current, old spec
  // control thread:
  // - if old is set, do atomic swap to temp ptr, then discard it.
  // - when setting new, do atomic swap from temp into new. if there was an
  //   existing new, discard it (it has never been used).
  // audio thread:
  // - do atomic swap of new into temp ptr. if set, do atomic swap of current into
  //   old, then assert that current is null. set current to temp ptr.
  // see std::atomic
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

Status VM::process_block() {
  Program *program = _program.get();
  if (program == nullptr) {
    return Status::Ok();
  }

  uint32_t new_block_size = _block_size.load();
  if (new_block_size != program->block_size) {
    log(LogLevel::INFO,
	"Block size changed %d -> %d", program->block_size, new_block_size);
    program->block_size = new_block_size;

    for(auto& buf : program->buffers) {
      buf->allocate(new_block_size);
    }
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

    // TODO: replace switch by function pointer in opcodes table. functions
    // live in opcodes.cc
    // use struct ProgramState for program ptr, p, end, ...
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
