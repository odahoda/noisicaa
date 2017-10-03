#include "noisicaa/audioproc/vm/misc.h"
#include "noisicaa/audioproc/vm/processor_sample_player.h"

namespace noisicaa {

ProcessorSamplePlayer::ProcessorSamplePlayer(const string& node_id, HostData *host_data)
  : ProcessorCSoundBase(node_id, "noisicaa.audioproc.vm.processor.sample_player", host_data) {}

Status ProcessorSamplePlayer::setup(const ProcessorSpec* spec) {
  Status status = ProcessorCSoundBase::setup(spec);
  if (status.is_error()) { return status; }

  StatusOr<string> stor_path = get_string_parameter("sample_path");
  if (stor_path.is_error()) { return stor_path; }
  string path = stor_path.result();

  // TODO:
  // - get sample attributes using sndfile
  // - explicitly set table size, so loading is not deferred.
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
  if (iVelocity == 0) then
    iAmp = 0.0
  else
    iAmp = 0.5 * db(-20 * log10(127^2 / iVelocity^2))
  endif
  iChannels = ftchnls(1)
  if (iChannels == 1) then
    aOut loscil3 iAmp, iFreq, 1, 261.626, 0
    gaOutL = gaOutL + aOut
    gaOutR = gaOutR + aOut
  elseif (iChannels == 2) then
    aOutL, aOutR loscil3 iAmp, iFreq, 1, 220, 0
    gaOutL = gaOutL + aOutL
    gaOutR = gaOutR + aOutR
  endif
endin
)---";

  string score = sprintf("f 1 0 0 -1 \"%s\" 0 0 0\n", path.c_str());

  // first note will fail, because ftable is not yet loaded.
  // play a silent note to trigger ftable initialization.
  score += "i 1 0 0.01 40 0\n";

  status = set_code(orchestra, score);
  if (status.is_error()) { return status; }

  return Status::Ok();
}

void ProcessorSamplePlayer::cleanup() {
  ProcessorCSoundBase::cleanup();
}

}
