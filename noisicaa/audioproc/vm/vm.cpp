#include <stdio.h>
#include <string.h>
#include <unistd.h>

#include "noisicaa/core/perf_stats.h"
#include "noisicaa/core/status.h"
#include "noisicaa/audioproc/vm/misc.h"
#include "noisicaa/audioproc/vm/vm.h"
#include "noisicaa/audioproc/vm/host_data.h"
#include "noisicaa/audioproc/vm/opcodes.h"
#include "noisicaa/audioproc/vm/block_context.h"
#include "noisicaa/audioproc/vm/backend.h"
#include "noisicaa/audioproc/vm/processor.h"

namespace noisicaa {

Program::Program(Logger* logger, uint32_t version)
  : version(version),
    _logger(logger) {
  _logger->info("Created program v%d", version);
}

Program::~Program() {
  _logger->info("Deleted program v%d", version);
}

Status Program::setup(HostData* host_data, const Spec* s, uint32_t block_size) {
  spec.reset(s);
  this->block_size = block_size;

  for (int i = 0 ; i < spec->num_buffers() ; ++i) {
    unique_ptr<Buffer> buf(new Buffer(host_data, spec->get_buffer(i)));
    Status status = buf->allocate(block_size);
    if (status.is_error()) { return status; }
    buffers.emplace_back(buf.release());
  }

  return Status::Ok();
}

VM::VM(HostData* host_data)
  : _logger(LoggerRegistry::get_logger("noisicaa.audioproc.vm.vm")),
    _host_data(host_data),
    _block_size(256),
    _next_program(nullptr),
    _current_program(nullptr),
    _old_program(nullptr) {
}

VM::~VM() {
  cleanup();
}

Status VM::setup() {
  return Status::Ok();
}

void VM::cleanup() {
  Program* program = _next_program.exchange(nullptr);
  if (program != nullptr) {
    delete program;
  }
  program = _current_program.exchange(nullptr);
  if (program != nullptr) {
    delete program;
  }
  program = _old_program.exchange(nullptr);
  if (program != nullptr) {
    delete program;
  }
}

Status VM::add_processor(Processor* processor) {
  unique_ptr<Processor> ptr(processor);
  assert(_processors.find(processor->id()) == _processors.end());
  _processors.emplace(
       processor->id(), unique_ptr<ActiveProcessor>(new ActiveProcessor(ptr.release())));
  return Status::Ok();
}

Status VM::add_control_value(ControlValue* cv) {
  unique_ptr<ControlValue> ptr(cv);
  assert(_control_values.find(cv->name()) == _control_values.end());
  _control_values.emplace(
       cv->name(), unique_ptr<ActiveControlValue>(new ActiveControlValue(ptr.release())));
  return Status::Ok();
}

Status VM::set_block_size(uint32_t block_size) {
  _block_size.store(block_size);
  return Status::Ok();
}

void VM::activate_program(Program* program) {
  for (int i = 0 ; i < program->spec->num_processors() ; ++i) {
    Processor* processor = program->spec->get_processor(i);
    ActiveProcessor* active_processor = _processors[processor->id()].get();
    assert(active_processor != nullptr);
    ++active_processor->ref_count;
  }

  for (int i = 0 ; i < program->spec->num_control_values() ; ++i) {
    ControlValue* cv = program->spec->get_control_value(i);
    ActiveControlValue* active_cv = _control_values[cv->name()].get();
    assert(active_cv != nullptr);
    ++active_cv->ref_count;
  }
}

void VM::deactivate_program(Program* program) {
  for (int i = 0 ; i < program->spec->num_processors() ; ++i) {
    Processor* processor = program->spec->get_processor(i);
    const auto& it = _processors.find(processor->id());
    assert(it != _processors.end());
    ActiveProcessor* active_processor = it->second.get();
    --active_processor->ref_count;
    if (active_processor->ref_count == 0) {
      _processors.erase(it);
    }
  }

  for (int i = 0 ; i < program->spec->num_control_values() ; ++i) {
    ControlValue* cv = program->spec->get_control_value(i);
    const auto& it = _control_values.find(cv->name());
    assert(it != _control_values.end());
    ActiveControlValue* active_cv = it->second.get();
    --active_cv->ref_count;
    if (active_cv->ref_count == 0) {
      _control_values.erase(it);
    }
  }
}

Status VM::set_spec(const Spec* spec) {
  unique_ptr<Program> program(new Program(_logger, _program_version++));

  Status status = program->setup(_host_data, spec, _block_size);
  if (status.is_error()) { return status; }

  activate_program(program.get());

  // Discard any next program, which hasn't been picked up by the audio thread.
  Program* prev_next_program = _next_program.exchange(nullptr);
  if (prev_next_program != nullptr) {
    deactivate_program(prev_next_program);
    delete prev_next_program;
  }

  // Discard program, which the audio thread doesn't use anymore.
  Program* old_program = _old_program.exchange(nullptr);
  if (old_program != nullptr) {
    deactivate_program(old_program);
    delete old_program;
  }

  prev_next_program = _next_program.exchange(program.release());
  assert(prev_next_program == nullptr);

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
  Program* program = _current_program.load();
  if (program == nullptr) {
    return nullptr;
  }

  StatusOr<int> stor_idx = program->spec->get_buffer_idx(name);
  if (stor_idx.is_error()) { return nullptr; }
  return program->buffers[stor_idx.result()].get();
}

// Status VM::set_float_control_value(const string& name, float value) {
//   lock_guard<mutex> lock(_control_values_mutex);

//   const auto& it = _control_values.find(name);
//   if (it == _control_values.end()) {
//     _control_values.emplace(name, unique_ptr<ControlValue>(new FloatControlValue(value)));
//     return Status::Ok();
//   }

//   ControlValue* cv = it->second.get();
//   if (cv->type() != ControlValue::Float) {
//     return Status::Error("Control value '%s' is not of type Float.", name.c_str());
//   }

//   dynamic_cast<FloatControlValue*>(cv)->set_value(value);
//   return Status::Ok();
// }

// StatusOr<float> VM::get_float_control_value(const string& name) {
//   lock_guard<mutex> lock(_control_values_mutex);

//   const auto& it = _control_values.find(name);
//   if (it == _control_values.end()) {
//     return Status::Error("Control value '%s' not found.", name.c_str());
//   }

//   ControlValue* cv = it->second.get();
//   if (cv->type() != ControlValue::Float) {
//     return Status::Error("Control value '%s' is not of type Float.", name.c_str());
//   }

//   return dynamic_cast<FloatControlValue*>(cv)->value();
// }

// Status VM::delete_control_value(const string& name) {
//   lock_guard<mutex> lock(_control_values_mutex);

//   const auto& it = _control_values.find(name);
//   if (it == _control_values.end()) {
//     return Status::Error("Control value '%s' not found.", name.c_str());
//   }

//   _control_values.erase(it);
//   return Status::Ok();
// }

Status VM::process_block(BlockContext* ctxt) {
  // If there is a next program, make it the current. The current program becomes
  // the old program, which will eventually be destroyed in the main thread.
  // It must not happen that a next program is available, before an old one has
  // been disposed of.
  Program* program = _next_program.exchange(nullptr);
  if (program != nullptr) {
    _logger->info("Activate program v%d", program->version);
    Program* old_program = _current_program.exchange(program);
    old_program = _old_program.exchange(old_program);
    assert(old_program == nullptr);
  }

  program = _current_program.load();
  if (program == nullptr) {
    usleep(10000);
    return Status::Ok();
  }

  Backend *backend = _backend.get();
  if (backend == nullptr) {
    usleep(10000);
    return Status::Ok();
  }

  Status status = backend->begin_block(ctxt);
  if (status.is_error()) { return status; }
  auto end_block = scopeGuard([&]() {
      Status status = backend->end_block(ctxt);
      if (status.is_error()) {
	_logger->error("Ignore error in Backend::end_block(): %s", status.message().c_str());
      }
    });

  if (backend->stopped()) {
    _logger->debug("Backend stopped.");
    return Status::Ok();
  }

  bool run_init = false;

  if (!program->initialized) {
    run_init = true;
  }

  uint32_t new_block_size = _block_size.load();
  if (new_block_size != program->block_size) {
    _logger->info("Block size changed %d -> %d", program->block_size, new_block_size);
    program->block_size = new_block_size;

    for(auto& buf : program->buffers) {
      buf->allocate(new_block_size);
    }

    run_init = true;
  }

  ctxt->block_size = program->block_size;
  if (ctxt->block_size == 0) {
    return Status::Error("Invalid block_size 0");
  }
  _logger->debug("Process block [%d,%d]", ctxt->sample_pos, ctxt->block_size);

  const Spec* spec = program->spec.get();
  ProgramState state = { _logger, _host_data, program, backend, 0, false };
  while (!state.end) {
    if (state.p == spec->num_ops()) {
      break;
    }

    int p = state.p++;

    OpCode opcode = spec->get_opcode(p);
    OpSpec opspec = opspecs[opcode];
    if (run_init && opspec.init != nullptr) {
      Status status = opspec.init(ctxt, &state, spec->get_opargs(p));
      if (status.is_error()) { return status; }
    }
    if (opspec.run != nullptr) {
      char perf_label[PerfStats::NAME_LENGTH];
      snprintf(perf_label, PerfStats::NAME_LENGTH, "opcode(%s)", opspec.name);
      PerfTracker tracker(ctxt->perf.get(), perf_label);
      Status status = opspec.run(ctxt, &state, spec->get_opargs(p));
      if (status.is_error()) { return status; }
    }
  }

  if (run_init) {
    program->initialized = true;
  }

  end_block.dismiss();
  status = backend->end_block(ctxt);
  if (status.is_error()) { return status; }

  return Status::Ok();
}

}  // namespace noisicaa
