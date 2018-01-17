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

#include <string>
#include <ctype.h>
#include <stdint.h>
#include "noisicaa/core/status.h"
#include "noisicaa/audioproc/vm/misc.h"
#include "noisicaa/audioproc/vm/processor_custom_csound.h"
#include "noisicaa/audioproc/vm/processor_spec.h"

namespace {

using namespace std;

string port_name_to_csound_label(const string &port_name) {
  string result;
  bool was_alpha = false;
  for (const auto& c : port_name) {
    bool is_alpha = isalpha(c);
    if (is_alpha && !was_alpha) {
      result += toupper(c);
    } else if (is_alpha) {
      result += c;
    }
    was_alpha = is_alpha;
  }

  return result;
}

}  // namespace

namespace noisicaa {

ProcessorCustomCSound::ProcessorCustomCSound(const string& node_id, HostData *host_data)
  : ProcessorCSoundBase(node_id, "noisicaa.audioproc.vm.processor.custom_csound", host_data) {}

Status ProcessorCustomCSound::setup(const ProcessorSpec* spec) {
  Status status = ProcessorCSoundBase::setup(spec);
  RETURN_IF_ERROR(status);

  StatusOr<string> stor_orchestra = get_string_parameter("csound_orchestra");
  RETURN_IF_ERROR(stor_orchestra);
  string orchestra = stor_orchestra.result();

  StatusOr<string> stor_score = get_string_parameter("csound_score");
  RETURN_IF_ERROR(stor_score);
  string score = stor_score.result();

  string orchestra_preamble = "0dbfs = 1.0\nksmps = 32\nnchnls = 2\n";

  for (uint32_t i = 0 ; i < _spec->num_ports() ; ++i) {
    const auto& port_spec = _spec->get_port(i);

    if (port_spec.type() == PortType::audio
        && port_spec.direction() == PortDirection::Input) {
      orchestra_preamble += sprintf(
          "ga%s chnexport \"%s\", 1\n",
          port_name_to_csound_label(port_spec.name()).c_str(),
          port_spec.name().c_str());
    } else if (port_spec.type() == PortType::audio
               && port_spec.direction() == PortDirection::Output) {
      orchestra_preamble += sprintf(
          "ga%s chnexport \"%s\", 2\n",
          port_name_to_csound_label(port_spec.name()).c_str(),
          port_spec.name().c_str());
    } else if (port_spec.type() == PortType::aRateControl
               && port_spec.direction() == PortDirection::Input) {
      orchestra_preamble += sprintf(
          "ga%s chnexport \"%s\", 1\n",
          port_name_to_csound_label(port_spec.name()).c_str(),
          port_spec.name().c_str());
    } else if (port_spec.type() == PortType::aRateControl
               && port_spec.direction() == PortDirection::Output) {
      orchestra_preamble += sprintf(
          "ga%s chnexport \"%s\", 2\n",
          port_name_to_csound_label(port_spec.name()).c_str(),
          port_spec.name().c_str());
    } else if (port_spec.type() == PortType::atomData
               && port_spec.direction() == PortDirection::Input) {
    } else {
      return ERROR_STATUS("Port %s not supported", port_spec.name().c_str());
    }
  }

  status = set_code(orchestra_preamble + orchestra, score);
  RETURN_IF_ERROR(status);

  return Status::Ok();
}

void ProcessorCustomCSound::cleanup() {
  ProcessorCSoundBase::cleanup();
}

}
