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
#include "noisicaa/core/scope_guard.h"
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

string Spec::dump(HostSystem* host_system) const {
  string out = "";

  if (_buffers.size() > 0) {
    out += "Buffers:\n";
    unsigned int i = 0;
    for (const auto& buf : _buffers) {
      out += sprintf(
          "% 3u %s [%d bytes]\n",
          i, pb::PortDescription::Type_Name(buf->type()).c_str(), buf->size(host_system));
      ++i;
    }
  }

  if (_processors.size() > 0) {
    out += "Processors:\n";
    unsigned int i = 0;
    for (const auto& proc : _processors) {
      out += sprintf(
          "% 3u %016lx [node_id=%s, state=%s]\n",
          i, proc->id(), proc->node_id().c_str(), proc->state_name(proc->state()));
      ++i;
    }
  }

  if (_control_values.size() > 0) {
    out += "Control Values:\n";
    unsigned int i = 0;
    for (const auto& cv : _control_values) {
      out += sprintf(
          "% 3u %s [type=%s, value=%s, generation=%d]\n",
          i, cv->name().c_str(), cv->type_name(), cv->formatted_value().c_str(), cv->generation());
      ++i;
    }
  }

  if (_child_realms.size() > 0) {
    out += "Child Realms:\n";
    unsigned int i = 0;
    for (const auto& cr : _child_realms) {
      out += sprintf(
                     "% 3u %s\n",
                     i, cr->name().c_str());
      ++i;
    }
  }

  if (_opcodes.size() > 0) {
    out += "Opcodes:\n";
    unsigned int i = 0;
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
        case 'r': {
          Realm* cr = _child_realms[arg.int_value()];
          args += sprintf("#REALM<%s>", cr->name().c_str());
          break;
        }
        case 'f':
          args += sprintf("%f", arg.float_value());
          break;
        case 's':
          args += sprintf("\"%s\"", arg.string_value().c_str());
          break;
        default:
          args += sprintf("?%c?", opspec.argspec[a]);
          break;
        }
      }

      out += sprintf("% 3u %s(%s)\n", i, opspec.name, args.c_str());
      ++i;
    }
  }

  return out;
}

Status Spec::append_opcode(OpCode opcode, const vector<OpArg>& args) {
  _opcodes.push_back({opcode, args});
  return Status::Ok();
}

Status Spec::append_buffer(const string& name, BufferType* type) {
  char* name_c = new char[name.size() + 1];
  memmove(name_c, name.c_str(), name.size() + 1);
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
