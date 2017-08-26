#include "vm.h"

#include <stdio.h>
#include <string.h>

#include "status.h"
#include "misc.h"
#include "host_data.h"
#include "opcodes.h"
#include "block_context.h"
#include "backend.h"
#include "processor.h"

using namespace std;

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

VM::VM(HostData* host_data)
  : _host_data(host_data),
    _block_size(256) {
}

VM::~VM() {
}

Status VM::setup() {
  return Status::Ok();
}

void VM::cleanup() {
}

Processor* VM::create_processor(const string& name) {
  return Processor::create(_host_data, name);
}

Status VM::add_processor(Processor* processor) {
  assert(_processors.find(processor->id()) == _processors.end());
  _processors.emplace(processor->id(), new ActiveProcessor(processor));
  return Status::Ok();
}

Status VM::set_block_size(uint32_t block_size) {
  _block_size.store(block_size);
  return Status::Ok();
}

Status VM::set_spec(const Spec* spec) {
  unique_ptr<Program> program(new Program);

  Status status = program->setup(spec, _block_size);
  if (status.is_error()) { return status; }

  if (_program.get() != nullptr) {
    for (int i = 0 ; i < _program->spec->num_processors() ; ++i) {
      Processor* processor = _program->spec->get_processor(i);
      const auto& it = _processors.find(processor->id());
      assert(it != _processors.end());
      ActiveProcessor* active_processor = it->second.get();
      --active_processor->ref_count;
      if (active_processor->ref_count == 0) {
	_processors.erase(it);
      }
    }
  }

  for (int i = 0 ; i < spec->num_processors() ; ++i) {
    Processor* processor = spec->get_processor(i);
    ActiveProcessor* active_processor = _processors[processor->id()].get();
    assert(active_processor != nullptr);
    ++active_processor->ref_count;
  }

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

Status VM::set_backend(Backend* backend) {
  unique_ptr<Backend> be(backend);

  // TODO: use same lockfree life cycle, as for the spec

  Status status = be->setup(this);
  if (status.is_error()) { return status; }

  if (_backend.get() != nullptr) {
    _backend->cleanup();
    _backend.reset();
  }

  _backend.reset(be.release());
  return Status::Ok();
}

Buffer* VM::get_buffer(const string& name) {
  if (_program.get() == nullptr) {
    return nullptr;
  }

  int idx = _program->spec->get_buffer_idx(name);
  return _program->buffers[idx].get();
}

Status VM::process_block(BlockContext* ctxt) {
  Program *program = _program.get();
  if (program == nullptr) {
    return Status::Ok();
  }

  Backend *backend = _backend.get();
  if (backend == nullptr) {
    return Status::Ok();
  }

  Status status = backend->begin_block();
  if (status.is_error()) { return status; }
  auto end_block = scopeGuard([&]() {
      Status status = backend->end_block();
      if (status.is_error()) {
	log(LogLevel::ERROR, "Ignore error in Backend::end_block(): %s", status.message().c_str());
      }
    });

  bool run_init = false;

  if (!program->initialized) {
    run_init = true;
  }

  uint32_t new_block_size = _block_size.load();
  if (new_block_size != program->block_size) {
    log(LogLevel::INFO,
	"Block size changed %d -> %d", program->block_size, new_block_size);
    program->block_size = new_block_size;

    for(auto& buf : program->buffers) {
      buf->allocate(new_block_size);
    }

    run_init = true;
  }

  ctxt->block_size = program->block_size;

  const Spec* spec = program->spec.get();
  ProgramState state = { program, backend, 0, false };
  while (!state.end) {
    if (state.p == spec->num_ops()) {
      break;
    }

    int p = state.p;
    ++state.p;

    OpCode opcode = spec->get_opcode(p);
    OpSpec opspec = opspecs[opcode];
    if (run_init && opspec.init != nullptr) {
      Status status = opspec.init(ctxt, &state, spec->get_opargs(p));
      if (status.is_error()) { return status; }
    }
    if (opspec.run != nullptr) {
      Status status = opspec.run(ctxt, &state, spec->get_opargs(p));
      if (status.is_error()) { return status; }
    }
  }

  if (run_init) {
    program->initialized = true;
  }

  end_block.dismiss();
  status = backend->end_block();
  if (status.is_error()) { return status; }

  return Status::Ok();
}

}  // namespace noisicaa
