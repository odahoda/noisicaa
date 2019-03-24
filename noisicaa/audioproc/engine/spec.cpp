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

#include <stdarg.h>
#include "noisicaa/core/logging.h"
#include "noisicaa/audioproc/engine/spec.h"
#include "noisicaa/audioproc/engine/control_value.h"
#include "noisicaa/audioproc/engine/processor.h"
#include "noisicaa/audioproc/engine/realm.h"

namespace noisicaa {

Spec::Spec() {
}

Spec::~Spec() {
  for(const auto& it : _buffer_map) {
    delete it.first;
  }
  _buffer_map.clear();
}

string Spec::dump() const {
  string out = "";

  int i = 0;
  for (const auto& opcode : _opcodes) {
    const auto& opspec = opspecs[opcode.opcode];

    string args = "";
    for (size_t a = 0 ; a < opcode.args.size() ; ++a) {
      const auto& arg = opcode.args[a];

      if (a > 0) {
        args += ", ";
      }

      switch (opspec.argspec[a]) {
      case 'i':
        args += sprintf("%ld", arg.int_value());
        break;
      case 'b': {
        args += sprintf("#BUF<%d>", arg.int_value());
        break;
      }
      case 'p': {
        Processor* processor = _processors[arg.int_value()];
        args += sprintf("#PROC<%016lx>", processor->id());
        break;
      }
      case 'c': {
        ControlValue* cv = _control_values[arg.int_value()];
        args += sprintf("#CV<%s>", cv->name().c_str());
        break;
      }
      case 'f':
        args += sprintf("%f", arg.float_value());
        break;
      case 's':
        args += sprintf("\"%s\"", arg.string_value().c_str());
        break;
      }
    }

    out += sprintf("% 3d %s(%s)\n", i, opspec.name, args.c_str());
    ++i;
  }

  return out;
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
      StatusOr<int> stor_value = get_buffer_idx(buf_name);
      RETURN_IF_ERROR(stor_value);
      args.emplace_back(OpArg((int64_t)stor_value.result()));
      break;
    }
    case 'p': {
      Processor* processor = va_arg(values, Processor*);
      StatusOr<int> stor_value = get_processor_idx(processor);
      RETURN_IF_ERROR(stor_value);
      args.emplace_back(OpArg((int64_t)stor_value.result()));
      break;
    }
    case 'c': {
      ControlValue* cv = va_arg(values, ControlValue*);
      StatusOr<int> stor_value = get_control_value_idx(cv);
      RETURN_IF_ERROR(stor_value);
      args.emplace_back(OpArg((int64_t)stor_value.result()));
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

  return append_opcode_args(opcode, args);
}

Status Spec::append_opcode_args(OpCode opcode, const vector<OpArg>& args) {
  _opcodes.push_back({opcode, args});
  return Status::Ok();
}

Status Spec::append_buffer(const string& name, BufferType* type) {
  char* name_c = new char[name.size() + 1];
  strcpy(name_c, name.c_str());
  _buffer_map[name_c] = _buffers.size();
  _buffers.emplace_back(type);
  return Status::Ok();
}

StatusOr<int> Spec::get_buffer_idx(const char* name) const {
  auto it = _buffer_map.find(name);
  if (it != _buffer_map.end()) {
    return it->second;
  }
  return ERROR_STATUS("Invalid buffer name %s", name);
}

Status Spec::append_control_value(ControlValue* cv) {
  _control_value_map[cv->name()] = _control_values.size();
  _control_values.emplace_back(cv);
  return Status::Ok();
}

StatusOr<int> Spec::get_control_value_idx(const ControlValue* cv) const {
  auto it = _control_value_map.find(cv->name());
  if (it != _control_value_map.end()) {
    return it->second;
  }
  return ERROR_STATUS("Invalid buffer name %s", cv->name().c_str());
}

Status Spec::append_processor(Processor* processor) {
  _processor_map[processor->id()] = _processors.size();
  _processors.push_back(processor);
  return Status::Ok();
}

StatusOr<int> Spec::get_processor_idx(const Processor* processor) {
  auto it = _processor_map.find(processor->id());
  if (it != _processor_map.end()) {
    return it->second;
  }
  return ERROR_STATUS("Invalid processor %016llx", processor->id());
}

Status Spec::append_child_realm(Realm* child_realm) {
  _child_realm_map[child_realm->name()] = _child_realms.size();
  _child_realms.push_back(child_realm);
  return Status::Ok();
}

StatusOr<int> Spec::get_child_realm_idx(const Realm* child_realm) {
  auto it = _child_realm_map.find(child_realm->name());
  if (it != _child_realm_map.end()) {
    return it->second;
  }
  return ERROR_STATUS("Invalid child realm %s", child_realm->name().c_str());
}

}  // namespace noisicaa
