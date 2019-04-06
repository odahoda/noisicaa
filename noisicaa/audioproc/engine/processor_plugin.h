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

#ifndef _NOISICAA_AUDIOPROC_ENGINE_PROCESSOR_PLUGIN_H
#define _NOISICAA_AUDIOPROC_ENGINE_PROCESSOR_PLUGIN_H

#include <stdint.h>
#include <chrono>
#include <map>
#include <string>
#include "noisicaa/core/status.h"
#include "noisicaa/audioproc/engine/buffers.h"
#include "noisicaa/audioproc/engine/processor.h"

namespace noisicaa {

using namespace std;

class BlockContext;
class HostSystem;

class ProcessorPlugin : public Processor {
public:
  ProcessorPlugin(
      const string& realm_name, const string& node_id, HostSystem* host_system,
      const pb::NodeDescription& desc);

protected:
  Status setup_internal() override;
  void cleanup_internal() override;
  Status set_parameters_internal(const pb::NodeParameters& parameters);
  Status connect_port_internal(BlockContext* ctxt, uint32_t port_idx, BufferPtr buf) override;
  Status process_block_internal(BlockContext* ctxt, TimeMapper* time_mapper) override;

private:
  typedef chrono::high_resolution_clock::time_point deadline_t;

  Status pipe_open(const string& path);
  void pipe_close();
  Status pipe_write(const char* data, size_t size, deadline_t deadline);

  int _pipe = -1;
  map<uint32_t, size_t> _buffer_map;
  bool _update_memmap = false;
};

}  // namespace noisicaa

#endif
