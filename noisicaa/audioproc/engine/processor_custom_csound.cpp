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
#include "noisicaa/audioproc/engine/misc.h"
#include "noisicaa/audioproc/engine/processor_custom_csound.h"

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

ProcessorCustomCSound::ProcessorCustomCSound(
    const string& node_id, HostSystem *host_system, const pb::NodeDescription& desc)
  : ProcessorCSoundBase(
        node_id, "noisicaa.audioproc.engine.processor.custom_csound", host_system, desc) {}

Status ProcessorCustomCSound::setup_internal() {
  RETURN_IF_ERROR(ProcessorCSoundBase::setup_internal());

  if (!_desc.has_csound()) {
    return ERROR_STATUS("NodeDescription misses csound field.");
  }

  string orchestra_preamble = "0dbfs = 1.0\nksmps = 32\nnchnls = 2\n";

  for (int i = 0 ; i < _desc.ports_size() ; ++i) {
    const auto& port = _desc.ports(i);

    if (port.type() == pb::PortDescription::AUDIO
        && port.direction() == pb::PortDescription::INPUT) {
      orchestra_preamble += sprintf(
          "ga%s chnexport \"%s\", 1\n",
          port_name_to_csound_label(port.name()).c_str(),
          port.name().c_str());
    } else if (port.type() == pb::PortDescription::AUDIO
               && port.direction() == pb::PortDescription::OUTPUT) {
      orchestra_preamble += sprintf(
          "ga%s chnexport \"%s\", 2\n",
          port_name_to_csound_label(port.name()).c_str(),
          port.name().c_str());
    } else if (port.type() == pb::PortDescription::ARATE_CONTROL
               && port.direction() == pb::PortDescription::INPUT) {
      orchestra_preamble += sprintf(
          "ga%s chnexport \"%s\", 1\n",
          port_name_to_csound_label(port.name()).c_str(),
          port.name().c_str());
    } else if (port.type() == pb::PortDescription::ARATE_CONTROL
               && port.direction() == pb::PortDescription::OUTPUT) {
      orchestra_preamble += sprintf(
          "ga%s chnexport \"%s\", 2\n",
          port_name_to_csound_label(port.name()).c_str(),
          port.name().c_str());
    } else if (port.type() == pb::PortDescription::EVENTS
               && port.direction() == pb::PortDescription::INPUT) {
    } else {
      return ERROR_STATUS("Port %s not supported", port.name().c_str());
    }
  }

  RETURN_IF_ERROR(
      set_code(orchestra_preamble + _desc.csound().orchestra(), _desc.csound().score()));

  return Status::Ok();
}

void ProcessorCustomCSound::cleanup_internal() {
  ProcessorCSoundBase::cleanup_internal();
}

}
