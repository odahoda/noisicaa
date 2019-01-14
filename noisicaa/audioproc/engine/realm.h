// -*- mode: c++ -*-

/*
 * @begin:license
 *
 * Copyright (c) 2015-2019, Benjamin Niemann <pink@odahoda.de>
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

#ifndef _NOISICAA_AUDIOPROC_ENGINE_REALM_H
#define _NOISICAA_AUDIOPROC_ENGINE_REALM_H

#include <atomic>
#include <memory>
#include <mutex>
#include <string>
#include <vector>
#include <stdint.h>
#include "noisicaa/core/refcount.h"
#include "noisicaa/core/status.h"
#include "noisicaa/core/slots.inl.h"
#include "noisicaa/audioproc/engine/processor.h"

namespace noisicaa {

using namespace std;

class Logger;
class Spec;
class ControlValue;
class BlockContext;
class HostSystem;
class NotificationQueue;
class Player;
class TimeMapper;
class BufferArena;
class Realm;

namespace pb {
class EngineNotification;
}

class Program {
public:
  Program(Logger* logger, uint32_t version);
  ~Program();

  Status setup(Realm* realm, HostSystem* host_system, const Spec* spec);

  uint32_t version = 0;
  bool initialized = false;
  unique_ptr<const Spec> spec;
  BufferArena* buffer_arena;
  vector<unique_ptr<Buffer>> buffers;
  unique_ptr<TimeMapper> time_mapper;

private:
  Logger* _logger;
};

struct ProgramState {
  Logger* logger;
  HostSystem* host_system;
  Program* program;
  int p;
  bool end;
};

struct ActiveProcessor {
  ActiveProcessor(Processor* processor, Slot<pb::EngineNotification>::Callback notification_callback);
  ~ActiveProcessor();

  Processor* processor;
  Slot<pb::EngineNotification>::Listener notification_listener;
  int ref_count;
};

struct ActiveControlValue {
  ActiveControlValue(ControlValue* cv);

  unique_ptr<ControlValue> control_value;
  int ref_count;
};

struct ActiveChildRealm {
  ActiveChildRealm(Realm* realm);
  ~ActiveChildRealm();

  Realm* child_realm;
  int ref_count;
};

class Realm : public RefCounted {
public:
  Realm(const string& name, HostSystem* host_system, Player* player);
  virtual ~Realm();

  const string& name() const { return _name; }

  Status setup();
  void cleanup() override;

  void clear_programs();

  void set_notification_callback(
      void (*callback)(void*, const string&), void* userdata);

  Status add_processor(Processor* processor);
  Status add_control_value(ControlValue* cv);
  Status add_child_realm(Realm* realm);
  StatusOr<Realm*> get_child_realm(const string& name);

  Status set_spec(const Spec* spec);

  Status set_float_control_value(const string& name, float value, uint32_t generation);

  Status send_processor_message(uint64_t processor_id, const string& msg_serialized);

  BlockContext* block_context() const { return _block_context.get(); }
  StatusOr<Program*> get_active_program();
  Status process_block(Program* program);

  Status run_maintenance();

  StatusOr<BufferArena*> get_buffer_arena(uint32_t size);
  Buffer* get_buffer(const char* name);

private:
  void activate_program(Program* program);
  void deactivate_program(Program* program);

  void notification_proxy(const pb::EngineNotification& notification);
  void (*_notification_callback)(void*, const string&) = nullptr;
  void* _notification_userdata = nullptr;

  string _name;
  Logger* _logger = nullptr;
  HostSystem* _host_system = nullptr;
  Player* _player = nullptr;
  unique_ptr<BlockContext> _block_context;
  vector<unique_ptr<BufferArena>> _buffer_arenas;
  atomic<Program*> _next_program;
  atomic<Program*> _current_program;
  atomic<Program*> _old_program;
  uint32_t _program_version = 0;
  map<uint64_t, unique_ptr<ActiveProcessor>> _processors;
  map<string, unique_ptr<ActiveControlValue>> _control_values;
  map<string, unique_ptr<ActiveChildRealm>> _child_realms;
};

}  // namespace noisicaa

#endif
