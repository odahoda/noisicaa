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

#ifndef _NOISICAA_AUDIOPROC_ENGINE_CSOUND_UTIL_H
#define _NOISICAA_AUDIOPROC_ENGINE_CSOUND_UTIL_H

#include <atomic>
#include <functional>
#include <string>
#include <vector>
#include <stdint.h>
#include "csound/csound.h"
#include "lv2/lv2plug.in/ns/ext/atom/forge.h"
#include "lv2/lv2plug.in/ns/ext/urid/urid.h"
#include "noisicaa/core/logging.h"
#include "noisicaa/core/status.h"
#include "noisicaa/node_db/node_description.pb.h"
#include "noisicaa/audioproc/engine/buffers.h"

namespace noisicaa {

using namespace std;

class HostSystem;
class BlockContext;
class TimeMapper;

class CSoundUtil {
public:
  CSoundUtil(HostSystem* host_system, function<void(LogLevel, const char*)> log_func);
  ~CSoundUtil();

  struct PortSpec {
    string name;
    pb::PortDescription::Type type;
    pb::PortDescription::Direction direction;
  };

  Status setup(const string& orchestra, const string& score, const vector<PortSpec>& ports);
  Status process_block(BlockContext* ctxt, TimeMapper* time_mapper, vector<BufferPtr>& buffers);

private:
  Logger* _logger;
  HostSystem* _host_system;
  function<void(LogLevel, const char*)> _log_func;

  static void _log_cb(CSOUND* csnd, int attr, const char* fmt, va_list args);
  void _log_cb(int attr, const char* fmt, va_list args);
  char _log_buf[10240];

  CSOUND* _csnd = nullptr;
  vector<MYFLT*> _channel_ptr;
  vector<int*> _channel_lock;

  vector<PortSpec> _ports;

  struct EventInputPort {
    LV2_Atom_Sequence* seq;
    LV2_Atom_Event* event;
    int instr;
  };
  vector<EventInputPort> _event_input_ports;
};

}  // namespace noisicaa

#endif
