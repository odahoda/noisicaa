// -*- mode: c++ -*-

/*
 * @begin:license
 *
 * Copyright (c) 2015-2017, Benjamin Niemann <pink@odahoda.de>
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

#ifndef _NOISICAA_AUDIOPROC_VM_PROCESSOR_H
#define _NOISICAA_AUDIOPROC_VM_PROCESSOR_H

#include <map>
#include <memory>
#include <string>
#include <stdint.h>
#include "noisicaa/core/logging.h"
#include "noisicaa/core/status.h"
#include "noisicaa/audioproc/vm/buffers.h"
#include "noisicaa/audioproc/vm/block_context.h"
#include "noisicaa/audioproc/vm/processor_spec.h"
#include "noisicaa/audioproc/vm/musical_time.h"
#include "noisicaa/audioproc/vm/misc.h"

namespace noisicaa {

using namespace std;

class HostData;
class NotificationQueue;
class TimeMapper;
namespace pb {
class ProcessorMessage;
}

class Processor {
public:
  Processor(const string& node_id, const char* logger_name, HostData* host_data);
  virtual ~Processor();

  static StatusOr<Processor*> create(
      const string& node_id, HostData* host_data, const string& name);

  uint64_t id() const { return _id; }
  const string& node_id() const { return _node_id; }

  StatusOr<string> get_string_parameter(const string& name);
  Status set_string_parameter(const string& name, const string& value);

  StatusOr<int64_t> get_int_parameter(const string& name);
  Status set_int_parameter(const string& name, int64_t value);

  StatusOr<float> get_float_parameter(const string& name);
  Status set_float_parameter(const string& name, float value);

  Status handle_message(const string& msg_serialized);

  virtual Status setup(const ProcessorSpec* spec);
  virtual void cleanup();

  virtual Status connect_port(uint32_t port_idx, BufferPtr buf) = 0;
  virtual Status run(BlockContext* ctxt, TimeMapper* time_mapper) = 0;

protected:
  virtual Status handle_message_internal(pb::ProcessorMessage* msg);

  Logger* _logger;
  HostData* _host_data;
  uint64_t _id;
  string _node_id;
  unique_ptr<const ProcessorSpec> _spec;
  map<string, string> _string_parameters;
  map<string, int64_t> _int_parameters;
  map<string, float> _float_parameters;

  static uint64_t new_id();
};

}  // namespace noisicaa

#endif
