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

#include "noisicaa/audioproc/engine/processor_csound.h"

namespace noisicaa {

ProcessorCSound::ProcessorCSound(
    const string& node_id, HostSystem *host_system, const pb::NodeDescription& desc)
  : ProcessorCSoundBase(node_id, "noisicaa.audioproc.engine.processor.csound", host_system, desc) {}

Status ProcessorCSound::setup_internal() {
  RETURN_IF_ERROR(ProcessorCSoundBase::setup_internal());

  if (!_desc.has_csound()) {
    return ERROR_STATUS("NodeDescription misses csound field.");
  }

  RETURN_IF_ERROR(set_code(_desc.csound().orchestra(), _desc.csound().score()));

  return Status::Ok();
}

void ProcessorCSound::cleanup_internal() {
  ProcessorCSoundBase::cleanup_internal();
}

}
