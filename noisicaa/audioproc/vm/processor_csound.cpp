#include "noisicaa/audioproc/vm/processor_csound.h"

namespace noisicaa {

ProcessorCSound::ProcessorCSound(const string& node_id, HostData *host_data)
  : ProcessorCSoundBase(node_id, "noisicaa.audioproc.vm.processor.csound", host_data) {}

Status ProcessorCSound::setup(const ProcessorSpec* spec) {
  Status status = ProcessorCSoundBase::setup(spec);
  if (status.is_error()) { return status; }

  StatusOr<string> stor_orchestra = get_string_parameter("csound_orchestra");
  if (stor_orchestra.is_error()) { return stor_orchestra; }
  string orchestra = stor_orchestra.result();

  StatusOr<string> stor_score = get_string_parameter("csound_score");
  if (stor_score.is_error()) { return stor_score; }
  string score = stor_score.result();

  status = set_code(orchestra, score);
  if (status.is_error()) { return status; }

  return Status::Ok();
}

void ProcessorCSound::cleanup() {
  ProcessorCSoundBase::cleanup();
}

}
