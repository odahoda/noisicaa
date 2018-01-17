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

#include "noisicaa/audioproc/vm/processor_null.h"

namespace noisicaa {

ProcessorNull::ProcessorNull(const string& node_id, HostData* host_data)
  : Processor(node_id, "noisicaa.audioproc.vm.processor.null", host_data) {}
ProcessorNull::~ProcessorNull() {}

Status ProcessorNull::setup(const ProcessorSpec* spec) {
  return Processor::setup(spec);
}

void ProcessorNull::cleanup() {
  Processor::cleanup();
}

Status ProcessorNull::connect_port(uint32_t port_idx, BufferPtr buf) {
  return Status::Ok();
}

Status ProcessorNull::run(BlockContext* ctxt, TimeMapper* time_mapper) {
  return Status::Ok();
}

}
