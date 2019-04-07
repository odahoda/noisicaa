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

#include "faust/dsp/dsp.h"
#include "faust/gui/meta.h"
#include "faust/gui/UI.h"

#include "noisicaa/core/perf_stats.h"
#include "noisicaa/host_system/host_system.h"
#include "noisicaa/audioproc/engine/processor_faust.h"

namespace noisicaa {

ProcessorFaust::ProcessorFaust(
    const string& realm_name, const string& node_id, HostSystem *host_system,
    const pb::NodeDescription& desc)
  : Processor(
      realm_name, node_id, "noisicaa.audioproc.engine.processor.faust", host_system, desc) {}

Status ProcessorFaust::setup_internal() {
  RETURN_IF_ERROR(Processor::setup_internal());

  _dsp.reset(create_dsp());
  _dsp->init(_host_system->sample_rate());

  int num_inputs = 0;
  int num_outputs = 0;
  for (const auto& port_desc : _desc.ports()) {
    if (port_desc.direction() == pb::PortDescription::INPUT) {
      if (port_desc.type() != pb::PortDescription::AUDIO
          && port_desc.type() != pb::PortDescription::ARATE_CONTROL) {
        return ERROR_STATUS(
             "Invalid input port type %s",
             pb::PortDescription::Type_Name(port_desc.type()).c_str());
      }
      ++num_inputs;
    } else {
      if (port_desc.type() != pb::PortDescription::AUDIO
          && port_desc.type() != pb::PortDescription::ARATE_CONTROL) {
        return ERROR_STATUS(
             "Invalid output port type %s",
             pb::PortDescription::Type_Name(port_desc.type()).c_str());
      }
      ++num_outputs;
    }
  }

  if (num_inputs != _dsp->getNumInputs()) {
    return ERROR_STATUS(
        "Number of input ports does not match (desc=%d vs. dsp=%d)",
        num_inputs, _dsp->getNumInputs());
  }

  if (num_outputs != _dsp->getNumOutputs()) {
    return ERROR_STATUS(
        "Number of output ports does not match (desc=%d vs. dsp=%d)",
        num_outputs, _dsp->getNumOutputs());
  }

  _inputs.reset(new float*[_dsp->getNumInputs()]);
  _outputs.reset(new float*[_dsp->getNumOutputs()]);

  return Status::Ok();
}

void ProcessorFaust::cleanup_internal() {
  _dsp.reset();
  _inputs.reset();
  _outputs.reset();

  Processor::cleanup_internal();
}

Status ProcessorFaust::connect_port_internal(
    BlockContext* ctxt, uint32_t port_idx, BufferPtr buf) {
  if (port_idx >= (uint32_t)_desc.ports_size()) {
    return ERROR_STATUS("Invalid port index %d", port_idx);
  }

  uint32_t in_idx = 0;
  uint32_t out_idx = 0;
  for (const auto& port_desc : _desc.ports()) {
    if (in_idx + out_idx == port_idx) {
      if (port_desc.direction() == pb::PortDescription::INPUT) {
        _inputs.get()[in_idx] = (float*)buf;
      } else {
        _outputs.get()[out_idx] = (float*)buf;
      }

      break;
    }

    if (port_desc.direction() == pb::PortDescription::INPUT) {
      ++in_idx;
    } else {
      ++out_idx;
    }
  }

  return Status::Ok();
}

Status ProcessorFaust::process_block_internal(BlockContext* ctxt, TimeMapper* time_mapper) {
  PerfTracker tracker(ctxt->perf.get(), "faust");

  float** inputs = _inputs.get();
  float** outputs = _outputs.get();

  for (int port_idx = 0 ; port_idx < _dsp->getNumInputs() ; ++port_idx) {
    if (inputs[port_idx] == nullptr) {
      return ERROR_STATUS("Input port %d not connected.", port_idx);
    }
  }

  for (int port_idx = 0 ; port_idx < _dsp->getNumOutputs() ; ++port_idx) {
    if (outputs[port_idx] == nullptr) {
      return ERROR_STATUS("Output port %d not connected.", port_idx);
    }
  }

  _dsp->compute(_host_system->block_size(), inputs, outputs);

  return Status::Ok();
}

}
