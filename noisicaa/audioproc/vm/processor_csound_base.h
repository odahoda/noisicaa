// -*- mode: c++ -*-

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

#ifndef _NOISICAA_AUDIOPROC_VM_PROCESSOR_CSOUND_BASE_H
#define _NOISICAA_AUDIOPROC_VM_PROCESSOR_CSOUND_BASE_H

#include <atomic>
#include <string>
#include <vector>
#include <stdint.h>
#include "csound/csound.h"
#include "lv2/lv2plug.in/ns/ext/atom/forge.h"
#include "lv2/lv2plug.in/ns/ext/urid/urid.h"
#include "noisicaa/core/status.h"
#include "noisicaa/audioproc/vm/buffers.h"
#include "noisicaa/audioproc/vm/processor.h"

namespace noisicaa {

using namespace std;

class HostData;
class BlockContext;

class ProcessorCSoundBase : public Processor {
public:
  ProcessorCSoundBase(const string& node_id, const char* logger_name, HostData* host_data);
  ~ProcessorCSoundBase() override;

  Status setup(const ProcessorSpec* spec) override;
  void cleanup() override;

  Status connect_port(uint32_t port_idx, BufferPtr buf) override;
  Status run(BlockContext* ctxt, TimeMapper* time_mapper) override;

protected:
  Status set_code(const string& orchestra, const string& score);

private:
  static void _log_cb(CSOUND* csnd, int attr, const char* fmt, va_list args);
  void _log_cb(int attr, const char* fmt, va_list args);
  char _log_buf[10240];

  class Instance {
  public:
    Instance(Logger* logger);
    ~Instance();

    Instance(const Instance&) = delete;
    Instance(Instance&&) = delete;
    Instance& operator=(const Instance&) = delete;
    Instance& operator=(Instance&&) = delete;

    CSOUND* csnd = nullptr;
    vector<MYFLT*> channel_ptr;
    vector<int*> channel_lock;

  private:
    Logger* _logger;
  };

  struct EventInputPort {
    LV2_Atom_Sequence* seq;
    LV2_Atom_Event* event;
    int instr;
  };

  vector<BufferPtr> _buffers;
  vector<EventInputPort> _event_input_ports;

  atomic<Instance*> _next_instance;
  atomic<Instance*> _current_instance;
  atomic<Instance*> _old_instance;
};

}  // namespace noisicaa

#endif
