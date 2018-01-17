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

#ifndef _NOISICAA_AUDIOPROC_VM_PROCESSOR_IPC_H
#define _NOISICAA_AUDIOPROC_VM_PROCESSOR_IPC_H

#include <string>
#include <vector>
#include <stdint.h>
#include "noisicaa/core/status.h"
#include "noisicaa/audioproc/vm/buffers.h"
#include "noisicaa/audioproc/vm/processor.h"
#include "noisicaa/audioproc/vm/audio_stream.h"

namespace noisicaa {

using namespace std;

class BlockContext;
class HostData;

class ProcessorIPC : public Processor {
public:
  ProcessorIPC(const string& node_id, HostData* host_data);
  ~ProcessorIPC() override;

  Status setup(const ProcessorSpec* spec) override;
  void cleanup() override;

  Status connect_port(uint32_t port_idx, BufferPtr buf) override;
  Status run(BlockContext* ctxt, TimeMapper* time_mapper) override;

private:
  BufferPtr _ports[2] = { nullptr, nullptr };
  unique_ptr<AudioStreamClient> _stream;
};

}  // namespace noisicaa

#endif
