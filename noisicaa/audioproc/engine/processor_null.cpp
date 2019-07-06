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

#include "noisicaa/audioproc/engine/processor_null.h"

namespace noisicaa {

ProcessorNull::ProcessorNull(
    const string& realm_name, const string& node_id, HostSystem* host_system,
    const pb::NodeDescription& desc)
  : Processor(
      realm_name, node_id, "noisicaa.audioproc.engine.processor.null", host_system, desc) {}
ProcessorNull::~ProcessorNull() {}

Status ProcessorNull::setup_internal() {
  return Processor::setup_internal();
}

void ProcessorNull::cleanup_internal() {
  Processor::cleanup_internal();
}

Status ProcessorNull::process_block_internal(BlockContext* ctxt, TimeMapper* time_mapper) {
  return Status::Ok();
}

}
