/*
 * @begin:license
 *
 * Copyright (c) 2015-2018, Benjamin Niemann <pink@odahoda.de>
 *
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation; either version 2 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License along
 * with this program; if not, write to the Free Software Foundation, Inc.,
 * 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
 *
 * @end:license
 */

#include <time.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <random>

#include "noisicaa/core/logging.h"
#include "noisicaa/core/perf_stats.h"
#include "noisicaa/core/status.h"
#include "noisicaa/host_system/host_system.h"
#include "noisicaa/audioproc/public/engine_notification.pb.h"
#include "noisicaa/audioproc/public/time_mapper.h"
#include "noisicaa/audioproc/engine/opcodes.h"
#include "noisicaa/audioproc/engine/block_context.h"
#include "noisicaa/audioproc/engine/processor.h"
#include "noisicaa/audioproc/engine/player.h"
#include "noisicaa/audioproc/engine/buffer_arena.h"
#include "noisicaa/audioproc/engine/spec.h"
#include "noisicaa/audioproc/engine/control_value.h"
#include "noisicaa/audioproc/engine/message_queue.h"
#include "noisicaa/audioproc/engine/realm.h"
#include "noisicaa/audioproc/engine/rtcheck.h"

namespace noisicaa {

Program::Program(Logger* logger, uint32_t version)
  : version(version),
    _logger(logger) {
  _logger->info("Created program v%d", version);
}

Program::~Program() {
  _logger->info("Deleted program v%d", version);
}

Status Program::setup(Realm* realm, HostSystem* host_system, const Spec* s) {
  spec.reset(s);

  uint32_t total_size = 0;
  for (int i = 0 ; i < spec->num_buffers() ; ++i) {
    total_size += spec->get_buffer(i)->size(host_system);
  }

  _logger->info("Require %lu bytes for buffers.", total_size);
  StatusOr<BufferArena*> stor_buffer_arena = realm->get_buffer_arena(total_size);
  RETURN_IF_ERROR(stor_buffer_arena);
  buffer_arena = stor_buffer_arena.result();

  BufferPtr data = buffer_arena->address();
  for (int i = 0 ; i < spec->num_buffers() ; ++i) {
    unique_ptr<Buffer> buf(new Buffer(host_system, spec->get_buffer(i), data));
    data += buf->size();
    buffers.emplace_back(buf.release());
  }

  time_mapper.reset(new TimeMapper(host_system->sample_rate()));
  time_mapper->set_bpm(spec->bpm());
  time_mapper->set_duration(spec->duration());

  return Status::Ok();
}

ActiveProcessor::ActiveProcessor(
    Processor* processor, Slot<pb::EngineNotification>::Callback notification_callback)
  : processor(processor),
    notification_listener(processor->notifications.connect(notification_callback)),
    ref_count(0) {
  processor->incref();
  // Emit correct state.
  // TODO: When we have async processor setup, remove this, as the notifications will come from
  // the background thread.

  pb::EngineNotification notification;
  auto nsc = notification.add_node_state_changes();
  nsc->set_realm(processor->realm_name());
  nsc->set_node_id(processor->node_id());
  switch (processor->state()) {
  case ProcessorState::INACTIVE: nsc->set_state(pb::NodeStateChange::INACTIVE); break;
  case ProcessorState::SETUP:    nsc->set_state(pb::NodeStateChange::SETUP); break;
  case ProcessorState::RUNNING:  nsc->set_state(pb::NodeStateChange::RUNNING); break;
  case ProcessorState::BROKEN:   nsc->set_state(pb::NodeStateChange::BROKEN); break;
  case ProcessorState::CLEANUP:  nsc->set_state(pb::NodeStateChange::CLEANUP); break;
  }
  notification_callback(notification);
}

ActiveProcessor::~ActiveProcessor() {
  processor->decref();
  processor->notifications.disconnect(notification_listener);
}

ActiveControlValue::ActiveControlValue(ControlValue* cv)
  : control_value(cv),
    ref_count(0) {}

ActiveChildRealm::ActiveChildRealm(Realm* realm)
  : child_realm(realm),
    ref_count(0) {
  child_realm->incref();
}

ActiveChildRealm::~ActiveChildRealm() {
  child_realm->decref();
}

Realm::Realm(const string& name, HostSystem* host_system, Player* player)
  : _name(name),
    _host_system(host_system),
    _player(player),
    _next_program(nullptr),
    _current_program(nullptr),
    _old_program(nullptr) {
  char logger_name[MaxLoggerNameLength];
  snprintf(logger_name, MaxLoggerNameLength, "noisicaa.audioproc.engine.realm[%s]", name.c_str());
  _logger = LoggerRegistry::get_logger(logger_name);
}

Realm::~Realm() {
  cleanup();
}

Status Realm::setup() {
  _block_context.reset(new BlockContext());
  _block_context->perf.reset(new PerfStats());

  _block_context->time_map.reset(new SampleTime[_host_system->block_size()]);
  SampleTime* it = _block_context->time_map.get();
  for (uint32_t i = 0 ; i < _host_system->block_size() ; ++it, ++i) {
      *it = SampleTime{ MusicalTime(-1, 1), MusicalTime(0, 1) };
    }

  return Status::Ok();
}

void Realm::cleanup() {
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

  _processors.clear();
  _control_values.clear();
  _child_realms.clear();

  _buffer_arenas.clear();
  _block_context.reset();
}

void Realm::clear_programs() {
  Program* program = _next_program.exchange(nullptr);
  if (program != nullptr) {
    deactivate_program(program);
    delete program;
  }
  program = _current_program.exchange(nullptr);
  if (program != nullptr) {
    deactivate_program(program);
    delete program;
  }
  program = _old_program.exchange(nullptr);
  if (program != nullptr) {
    deactivate_program(program);
    delete program;
  }

  assert(_processors.size() == 0);
  assert(_control_values.size() == 0);
  assert(_child_realms.size() == 0);
}

Status Realm::add_processor(Processor* processor) {
  if (_processors.count(processor->id()) != 0) {
    return ERROR_STATUS("Duplicate processor %llx", processor->id());
  }

  _logger->info("Activating processor %llx", processor->id());

  ActiveProcessor* active_processor = new ActiveProcessor(
      processor,
      std::bind(&Realm::notification_proxy, this, placeholders::_1));

  _processors.emplace(processor->id(), unique_ptr<ActiveProcessor>(active_processor));
  return Status::Ok();
}

void Realm::set_notification_callback(
    void (*callback)(void*, const string&), void* userdata) {
  assert(_notification_callback == nullptr);
  _notification_callback = callback;
  _notification_userdata = userdata;
}

void Realm::notification_proxy(const pb::EngineNotification& notification) {
  if (_notification_callback != nullptr) {
    string notification_serialized;
    assert(notification.SerializeToString(&notification_serialized));
    _notification_callback(_notification_userdata, notification_serialized);
  }
}

Status Realm::add_control_value(ControlValue* cv) {
  unique_ptr<ControlValue> ptr(cv);
  if (_control_values.count(cv->name()) != 0) {
    return ERROR_STATUS("Duplicate control value %s", cv->name().c_str());
  }

  _control_values.emplace(
       cv->name(), unique_ptr<ActiveControlValue>(new ActiveControlValue(ptr.release())));
  return Status::Ok();
}

Status Realm::add_child_realm(Realm* child) {
  unique_ptr<Realm> ptr(child);
  if (_child_realms.count(child->name()) != 0) {
    return ERROR_STATUS("Duplicate child realm %s", child->name().c_str());
  }

  _child_realms.emplace(
       child->name(), unique_ptr<ActiveChildRealm>(new ActiveChildRealm(ptr.release())));

  return Status::Ok();
}

StatusOr<Realm*> Realm::get_child_realm(const string& name) {
  const auto& it = _child_realms.find(name);
  if (it == _child_realms.end()) {
    return ERROR_STATUS("No child realm '%s'", name.c_str());
  }
  return it->second.get()->child_realm;
}

void Realm::activate_program(Program* program) {
  for (int i = 0 ; i < program->spec->num_processors() ; ++i) {
    Processor* processor = program->spec->get_processor(i);
    const auto& it = _processors.find(processor->id());
    assert(it != _processors.end());
    ActiveProcessor* active_processor = it->second.get();
    assert(active_processor != nullptr);
    ++active_processor->ref_count;
  }

  for (int i = 0 ; i < program->spec->num_control_values() ; ++i) {
    ControlValue* cv = program->spec->get_control_value(i);
    const auto& it = _control_values.find(cv->name());
    assert(it != _control_values.end());
    ActiveControlValue* active_cv = it->second.get();
    assert(active_cv != nullptr);
    ++active_cv->ref_count;
  }

  for (int i = 0 ; i < program->spec->num_child_realms() ; ++i) {
    Realm* realm = program->spec->get_child_realm(i);
    const auto& it = _child_realms.find(realm->name());
    assert(it != _child_realms.end());
    ActiveChildRealm* active_child_realm = it->second.get();
    assert(active_child_realm != nullptr);
    ++active_child_realm->ref_count;
  }
}

void Realm::deactivate_program(Program* program) {
  for (int i = 0 ; i < program->spec->num_processors() ; ++i) {
    Processor* processor = program->spec->get_processor(i);
    const auto& it = _processors.find(processor->id());
    assert(it != _processors.end());
    ActiveProcessor* active_processor = it->second.get();
    --active_processor->ref_count;
    if (active_processor->ref_count == 0) {
      _logger->info("Deactivating processor %llx", processor->id());
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
      _logger->info("Deactivating control value %s", cv->name().c_str());
      _control_values.erase(it);
    }
  }

  for (int i = 0 ; i < program->spec->num_child_realms() ; ++i) {
    Realm* realm = program->spec->get_child_realm(i);
    const auto& it = _child_realms.find(realm->name());
    assert(it != _child_realms.end());
    ActiveChildRealm* active_child_realm = it->second.get();
    --active_child_realm->ref_count;
    if (active_child_realm->ref_count == 0) {
      _logger->info("Deactivating child realm %s", realm->name().c_str());
      _child_realms.erase(it);
    }
  }
}

StatusOr<BufferArena*> Realm::get_buffer_arena(uint32_t size) {
  const uint32_t min_size = 1 << 16;
  if (size < min_size) {
    size = min_size;
  }

  for (auto& arena : _buffer_arenas) {
    if (arena->size() >= size) {
      return arena.get();
    }
  }

  unique_ptr<BufferArena> arena(new BufferArena(size, _logger));
  RETURN_IF_ERROR(arena->setup());
  _buffer_arenas.emplace_back(move(arena));
  return _buffer_arenas.back().get();
}

Status Realm::set_spec(const Spec* s) {
  unique_ptr<const Spec> spec(s);

  RETURN_IF_ERROR(spec->get_buffer_idx("sink:in:left"));
  RETURN_IF_ERROR(spec->get_buffer_idx("sink:in:right"));

  unique_ptr<Program> program(new Program(_logger, _program_version++));

  RETURN_IF_ERROR(program->setup(this, _host_system, spec.release()));

  _logger->info("Activate next program v%d", program->version);
  activate_program(program.get());

  // Discard any next program, which hasn't been picked up by the audio thread.
  Program* prev_next_program = _next_program.exchange(nullptr);
  if (prev_next_program != nullptr) {
    _logger->info("Deactivate unused program v%d", prev_next_program->version);
    deactivate_program(prev_next_program);
    delete prev_next_program;
  }

  // Discard program, which the audio thread doesn't use anymore.
  Program* old_program = _old_program.exchange(nullptr);
  if (old_program != nullptr) {
    _logger->info("Deactivate old program v%d", old_program->version);
    deactivate_program(old_program);
    delete old_program;
  }

  prev_next_program = _next_program.exchange(program.release());
  assert(prev_next_program == nullptr);

  return Status::Ok();
}

Buffer* Realm::get_buffer(const string& name) {
  Program* program = _current_program.load();
  if (program == nullptr) {
    return nullptr;
  }

  StatusOr<int> stor_idx = program->spec->get_buffer_idx(name);
  if (stor_idx.is_error()) { return nullptr; }
  return program->buffers[stor_idx.result()].get();
}

Status Realm::set_float_control_value(const string& name, float value, uint32_t generation) {
  const auto& it = _control_values.find(name);
  if (it == _control_values.end()) {
    return ERROR_STATUS("Control value '%s' not found.", name.c_str());
  }

  ControlValue* cv = it->second->control_value.get();
  if (cv->type() != ControlValueType::FloatCV) {
    return ERROR_STATUS("Control value '%s' is not of type Float.", name.c_str());
  }

  FloatControlValue* fcv = (FloatControlValue*)cv;
  if (generation > fcv->generation()) {
    fcv->set_value(value, generation);
  }
  return Status::Ok();
}

Status Realm::send_processor_message(uint64_t processor_id, const string& msg_serialized) {
  ActiveProcessor* active_processor = _processors[processor_id].get();
  assert(active_processor != nullptr);
  return active_processor->processor->handle_message(msg_serialized);
}

StatusOr<Program*> Realm::get_active_program() {
  // If there is a next program, make it the current. The current program becomes
  // the old program, which will eventually be destroyed in the main thread.
  // It must not happen that a next program is available, before an old one has
  // been disposed of.
  if (_old_program.load() == nullptr) {
    Program* program = _next_program.exchange(nullptr);
    if (program != nullptr) {
      _logger->info("Use program v%d", program->version);
      Program* old_program = _current_program.exchange(program);
      if (old_program) {
        _logger->info("Unuse program v%d", old_program->version);

        for (auto& buffer : old_program->buffers) {
          buffer->cleanup();
        }

        old_program = _old_program.exchange(old_program);
        assert(old_program == nullptr);
      }

      for (auto& buffer : program->buffers) {
        RETURN_IF_ERROR(buffer->setup());
      }
    }
  }

  return _current_program.load();
}

Status Realm::process_block(Program* program) {
  _block_context->buffer_arena = program->buffer_arena;

  bool run_init = false;

  if (!program->initialized) {
    run_init = true;
  }

  _logger->debug("Process block [%d,%d]", _block_context->sample_pos, _host_system->block_size());

  if (_player != nullptr) {
    PerfTracker tracker(_block_context->perf.get(), "fill_time_map");

    _player->fill_time_map(program->time_mapper.get(), _block_context.get());
  }

  const Spec* spec = program->spec.get();
  ProgramState state = { _logger, _host_system, program, 0, false };

  if (run_init) {
    while (state.p < spec->num_ops()) {
      int p = state.p++;

      OpCode opcode = spec->get_opcode(p);
      OpSpec opspec = opspecs[opcode];
      if (opspec.init != nullptr) {
        RETURN_IF_ERROR(opspec.init(_block_context.get(), &state, spec->get_opargs(p)));
      }
    }

    program->initialized = true;
    state.p = 0;
  }

  while (!state.end) {
    if (state.p == spec->num_ops()) {
      break;
    }

    int p = state.p++;

    OpCode opcode = spec->get_opcode(p);
    OpSpec opspec = opspecs[opcode];
    if (opspec.run != nullptr) {
      char perf_label[PerfStats::NAME_LENGTH];
      snprintf(perf_label, PerfStats::NAME_LENGTH, "opcode(%s)", opspec.name);
      PerfTracker tracker(_block_context->perf.get(), perf_label);
      RETURN_IF_ERROR(opspec.run(_block_context.get(), &state, spec->get_opargs(p)));
    }
  }

  _block_context->sample_pos += _host_system->block_size();

  return Status::Ok();
}

Status Realm::run_maintenance() {
  // Discard program, which the audio thread doesn't use anymore.
  Program* old_program = _old_program.exchange(nullptr);
  if (old_program != nullptr) {
    _logger->info("Deactivate old program v%d", old_program->version);
    deactivate_program(old_program);
    delete old_program;
  }

  return Status::Ok();
}

}  // namespace noisicaa
