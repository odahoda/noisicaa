#include <string>
#include <ctype.h>
#include <stdint.h>
#include "noisicaa/core/status.h"
#include "noisicore/misc.h"
#include "noisicore/processor_custom_csound.h"
#include "noisicore/processor_spec.h"

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

ProcessorCustomCSound::ProcessorCustomCSound(HostData *host_data)
  : ProcessorCSoundBase("noisicore.processor.custom_csound", host_data) {}

Status ProcessorCustomCSound::setup(const ProcessorSpec* spec) {
  Status status = ProcessorCSoundBase::setup(spec);
  if (status.is_error()) { return status; }

  StatusOr<string> stor_orchestra = get_string_parameter("csound_orchestra");
  if (stor_orchestra.is_error()) { return stor_orchestra; }
  string orchestra = stor_orchestra.result();

  StatusOr<string> stor_score = get_string_parameter("csound_score");
  if (stor_score.is_error()) { return stor_score; }
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
      return Status::Error("Port %s not supported", port_spec.name().c_str());
    }
  }

  status = set_code(orchestra_preamble + orchestra, score);
  if (status.is_error()) { return status; }

  return Status::Ok();
}

void ProcessorCustomCSound::cleanup() {
  ProcessorCSoundBase::cleanup();
}

}
