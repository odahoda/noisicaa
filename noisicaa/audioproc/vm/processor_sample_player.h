// -*- mode: c++ -*-

#ifndef _NOISICAA_AUDIOPROC_VM_PROCESSOR_SAMPLE_PLAYER_H
#define _NOISICAA_AUDIOPROC_VM_PROCESSOR_SAMPLE_PLAYER_H

#include "noisicaa/core/status.h"
#include "noisicaa/audioproc/vm/processor_csound_base.h"

namespace noisicaa {

using namespace std;

class HostData;
class ProcessorSpec;

class ProcessorSamplePlayer : public ProcessorCSoundBase {
public:
  ProcessorSamplePlayer(HostData* host_data);

  Status setup(const ProcessorSpec* spec) override;
  void cleanup() override;
};

}  // namespace noisicaa

#endif
