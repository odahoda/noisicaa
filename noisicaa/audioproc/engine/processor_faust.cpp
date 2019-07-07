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

#include <map>

#include "faust/dsp/dsp.h"
#include "faust/gui/meta.h"
#include "faust/gui/UI.h"

#include "noisicaa/core/perf_stats.h"
#include "noisicaa/host_system/host_system.h"
#include "noisicaa/audioproc/engine/processor_faust.h"

namespace noisicaa {

class FaustControls : public UI {
public:
  int num_controls() const {
    return _control_map.size();
  }

  float* get_control_ptr(const string& name) {
    return _control_map[name];
  }

  void openTabBox(const char* label) override {}
  void openHorizontalBox(const char* label) override {}
  void openVerticalBox(const char* label) override {}
  void closeBox() override {}

  void addButton(const char* label, float* zone) override {
    _control_map[label] = zone;
  }
  void addCheckButton(const char* label, float* zone) override {
    _control_map[label] = zone;
  }
  void addVerticalSlider(const char* label, float* zone, float init, float min, float max, float step) override {
    _control_map[label] = zone;
  }
  void addHorizontalSlider(const char* label, float* zone, float init, float min, float max, float step) override {
    _control_map[label] = zone;
  }
  void addNumEntry(const char* label, float* zone, float init, float min, float max, float step) override {
    _control_map[label] = zone;
  }

  void addHorizontalBargraph(const char* label, float* zone, float min, float max) override {
    _control_map[label] = zone;
  }
  void addVerticalBargraph(const char* label, float* zone, float min, float max) override {
    _control_map[label] = zone;
  }

  void addSoundfile(const char* label, const char* filename, Soundfile** sf_zone) override {}
  void declare(float* zone, const char* key, const char* val) override {}

private:
  map<string, float*> _control_map;
};

ProcessorFaust::ProcessorFaust(
    const string& realm_name, const string& node_id, HostSystem *host_system,
    const pb::NodeDescription& desc)
  : Processor(
      realm_name, node_id, "noisicaa.audioproc.engine.processor.faust", host_system, desc) {}

Status ProcessorFaust::setup_internal() {
  RETURN_IF_ERROR(Processor::setup_internal());

  _dsp.reset(create_dsp());
  _dsp->init(_host_system->sample_rate());

  FaustControls controls;
  _dsp->buildUserInterface(&controls);

  int dsp_ports = _dsp->getNumInputs() + _dsp->getNumOutputs() + controls.num_controls();
  if (dsp_ports != _desc.ports_size()) {
    return ERROR_STATUS("Port mismatch (desc=%d, dsp=%d)", _desc.ports_size(), dsp_ports);
  }

  _inputs.reset(new float*[_dsp->getNumInputs()]);
  _outputs.reset(new float*[_dsp->getNumOutputs()]);
  _controls.reset(new float*[controls.num_controls()]);

  int control_idx = 0;
  for (int port_idx = 0 ; port_idx < _desc.ports_size() ; ++port_idx) {
    const auto& port_desc = _desc.ports(port_idx);
    if (port_idx < _dsp->getNumInputs()) {
      if (port_desc.direction() != pb::PortDescription::INPUT) {
        return ERROR_STATUS(
             "Port %d: Expected INPUT port, got %s",
             port_idx, pb::PortDescription::Direction_Name(port_desc.direction()).c_str());
      }
      if (port_desc.type() != pb::PortDescription::AUDIO
          && port_desc.type() != pb::PortDescription::ARATE_CONTROL) {
        return ERROR_STATUS(
             "Port %d: Expected AUDIO/ARATE_CONTROL port, got %s",
             port_idx, pb::PortDescription::Type_Name(port_desc.type()).c_str());
      }
    } else if (port_idx < _dsp->getNumInputs() + _dsp->getNumOutputs()) {
      if (port_desc.direction() != pb::PortDescription::OUTPUT) {
        return ERROR_STATUS(
             "Port %d: Expected OUTPUT port, got %s",
             port_idx, pb::PortDescription::Direction_Name(port_desc.direction()).c_str());
      }
      if (port_desc.type() != pb::PortDescription::AUDIO
          && port_desc.type() != pb::PortDescription::ARATE_CONTROL) {
        return ERROR_STATUS(
             "Port %d: Expected AUDIO/ARATE_CONTROL port, got %s",
             port_idx, pb::PortDescription::Type_Name(port_desc.type()).c_str());
      }
    } else {
      if (port_desc.direction() != pb::PortDescription::INPUT) {
        return ERROR_STATUS(
             "Port %d: Expected INPUT port, got %s",
             port_idx, pb::PortDescription::Direction_Name(port_desc.direction()).c_str());
      }
      if (port_desc.type() != pb::PortDescription::KRATE_CONTROL) {
        return ERROR_STATUS(
             "Port %d: Expected KRATE_CONTROL port, got %s",
             port_idx, pb::PortDescription::Type_Name(port_desc.type()).c_str());
      }

      float* control_ptr = controls.get_control_ptr(port_desc.name());
      if (control_ptr == nullptr) {
        return ERROR_STATUS(
             "Port %d: Control '%s' not declared by DSP",
             port_idx, port_desc.name().c_str());
      }
      _controls.get()[control_idx] = control_ptr;
      ++control_idx;
    }
  }

  return Status::Ok();
}

void ProcessorFaust::cleanup_internal() {
  _dsp.reset();
  _inputs.reset();
  _outputs.reset();
  _controls.reset();

  Processor::cleanup_internal();
}

Status ProcessorFaust::process_block_internal(BlockContext* ctxt, TimeMapper* time_mapper) {
  PerfTracker tracker(ctxt->perf.get(), "faust");

  float** inputs = _inputs.get();
  float** outputs = _outputs.get();

  int input_idx = 0;
  int output_idx = 0;
  int control_idx = 0;
  for (int port_idx = 0 ; port_idx < _desc.ports_size() ; ++port_idx) {
    BufferPtr buf = _buffers[port_idx]->data();
    if (buf == nullptr) {
      return ERROR_STATUS("Port %d not connected.", port_idx);
    }

    if (port_idx < _dsp->getNumInputs()) {
      inputs[input_idx] = (float*)buf;
      ++input_idx;
    } else if (port_idx < _dsp->getNumInputs() + _dsp->getNumOutputs()) {
      outputs[output_idx] = (float*)buf;
      ++output_idx;
    } else {
      *(_controls.get()[control_idx]) = *((float*)buf);
      ++control_idx;
    }
  }

  _dsp->compute(_host_system->block_size(), inputs, outputs);

  return Status::Ok();
}

}
