#include "noisicaa/audioproc/vm/misc.h"
#include "noisicaa/audioproc/vm/processor_sample_player.h"

namespace noisicaa {

ProcessorSamplePlayer::ProcessorSamplePlayer(HostData *host_data)
  : ProcessorCSoundBase("noisicaa.audioproc.vm.processor.sample_player", host_data) {}

Status ProcessorSamplePlayer::setup(const ProcessorSpec* spec) {
  Status status = ProcessorCSoundBase::setup(spec);
  if (status.is_error()) { return status; }

  StatusOr<string> stor_path = get_string_parameter("sample_path");
  if (stor_path.is_error()) { return stor_path; }
  string path = stor_path.result();

  string orchestra = R"---(
0dbfs = 1.0
ksmps = 32
nchnls = 2
gaOutL chnexport "out:left", 2
gaOutR chnexport "out:right", 2
instr 1
  iPitch = p4
  iVelocity = p5
  iFreq = cpsmidinn(iPitch)
  iVolume = -20 * log10(127^2 / iVelocity^2)
  iChannels = ftchnls(1)
  if (iChannels == 1) then
    aOut loscil3 0.5 * db(iVolume), iFreq, 1, 261.626, 0
    gaOutL = aOut
    gaOutR = aOut
  elseif (iChannels == 2) then
    aOutL, aOutR loscil3 0.5 * db(iVolume), iFreq, 1, 220, 0
    gaOutL = aOutL
    gaOutR = aOutR
  endif
endin
)---";

  string score = sprintf("f 1 0 0 1 \"%s\" 0 0 0\n", path.c_str());

  status = set_code(orchestra, score);
  if (status.is_error()) { return status; }

  return Status::Ok();
}

void ProcessorSamplePlayer::cleanup() {
  ProcessorCSoundBase::cleanup();
}

}
