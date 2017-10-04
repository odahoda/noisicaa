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

#include "noisicaa/audioproc/vm/processor_csound.h"

namespace noisicaa {

ProcessorCSound::ProcessorCSound(const string& node_id, HostData *host_data)
  : ProcessorCSoundBase(node_id, "noisicaa.audioproc.vm.processor.csound", host_data) {}

Status ProcessorCSound::setup(const ProcessorSpec* spec) {
  Status status = ProcessorCSoundBase::setup(spec);
  RETURN_IF_ERROR(status);

  StatusOr<string> stor_orchestra = get_string_parameter("csound_orchestra");
  RETURN_IF_ERROR(stor_orchestra);
  string orchestra = stor_orchestra.result();

  StatusOr<string> stor_score = get_string_parameter("csound_score");
  RETURN_IF_ERROR(stor_score);
  string score = stor_score.result();

  status = set_code(orchestra, score);
  RETURN_IF_ERROR(status);

  return Status::Ok();
}

void ProcessorCSound::cleanup() {
  ProcessorCSoundBase::cleanup();
}

}
