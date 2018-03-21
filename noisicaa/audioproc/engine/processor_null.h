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

#ifndef _NOISICAA_AUDIOPROC_ENGINE_PROCESSOR_NULL_H
#define _NOISICAA_AUDIOPROC_ENGINE_PROCESSOR_NULL_H

#include <stdint.h>
#include "noisicaa/core/status.h"
#include "noisicaa/audioproc/engine/buffers.h"
#include "noisicaa/audioproc/engine/processor.h"

namespace noisicaa {

class BlockContext;
class HostSystem;

class ProcessorNull : public Processor {
public:
  ProcessorNull(const string& node_id, HostSystem* host_system, const pb::NodeDescription& desc);
  ~ProcessorNull() override;

protected:
  Status setup_internal() override;
  void cleanup_internal() override;
  Status connect_port_internal(BlockContext* ctxt, uint32_t port_idx, BufferPtr buf) override;
  Status process_block_internal(BlockContext* ctxt, TimeMapper* time_mapper) override;
};

}  // namespace noisicaa

#endif
