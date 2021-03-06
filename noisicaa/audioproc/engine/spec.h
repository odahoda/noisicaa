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

#ifndef _NOISICAA_AUDIOPROC_ENGINE_SPEC_H
#define _NOISICAA_AUDIOPROC_ENGINE_SPEC_H

#include <map>
#include <memory>
#include <vector>
#include <stdint.h>
#include "noisicaa/core/status.h"
#include "noisicaa/audioproc/public/musical_time.h"
#include "noisicaa/audioproc/engine/opcodes.h"

namespace noisicaa {

using namespace std;

class Logger;
class Processor;
class ControlValue;
class BufferType;
class Realm;
class HostSystem;

struct Instruction {
  OpCode opcode;
  vector<OpArg> args;
};

class Spec {
public:
  Spec();
  ~Spec();

  Spec(const Spec&) = delete;
  Spec operator=(const Spec&) = delete;

  string dump(HostSystem* host_system) const;

  void set_bpm(uint32_t bpm) { _bpm = bpm; }
  uint32_t bpm() const { return _bpm; }

  void set_duration(MusicalDuration duration) { _duration = duration; }
  MusicalDuration duration() const { return _duration; }

  Status append_opcode(OpCode opcode, const vector<OpArg>& args);
  int num_ops() const { return _opcodes.size(); }
  const vector<OpArg>& get_opargs(int idx) const { return _opcodes[idx].args; }
  OpCode get_opcode(int idx) const { return _opcodes[idx].opcode; }
  const OpArg& get_oparg(int idx, int arg) const { return _opcodes[idx].args[arg]; }

  Status append_buffer(const string& name, BufferType* type);
  int num_buffers() const { return _buffers.size(); }
  const BufferType* get_buffer(int idx) const { return _buffers[idx].get(); }
  StatusOr<int> get_buffer_idx(const char* name) const;

  Status append_control_value(ControlValue* cv);
  int num_control_values() const { return _control_values.size(); }
  ControlValue* get_control_value(int idx) const { return _control_values[idx]; }
  StatusOr<int> get_control_value_idx(const ControlValue* cv) const;

  Status append_processor(Processor* processor);
  int num_processors() const { return _processors.size(); }
  Processor* get_processor(int idx) const { return _processors[idx]; }
  StatusOr<int> get_processor_idx(const Processor* processor);

  Status append_child_realm(Realm* child_realm);
  int num_child_realms() const { return _child_realms.size(); }
  Realm* get_child_realm(int idx) const { return _child_realms[idx]; }
  StatusOr<int> get_child_realm_idx(const Realm* child_realms);

private:
  struct cmp_cstr {
    bool operator()(const char* a, const char* b) const {
      return strcmp(a, b) < 0;
    }
  };

  uint32_t _bpm = 120;
  MusicalDuration _duration = MusicalDuration(2, 1);

  vector<Instruction> _opcodes;

  vector<Processor*> _processors;
  map<uint64_t, int> _processor_map;

  vector<unique_ptr<const BufferType>> _buffers;
  map<const char*, int, cmp_cstr> _buffer_map;

  vector<ControlValue*> _control_values;
  map<string, int> _control_value_map;

  vector<Realm*> _child_realms;
  map<string, int> _child_realm_map;
};

}  // namespace noisicaa

#endif
