// -*- mode: c++ -*-

#ifndef _NOISICAA_AUDIOPROC_VM_PROCESSOR_CSOUND_H
#define _NOISICAA_AUDIOPROC_VM_PROCESSOR_CSOUND_H

#include "noisicaa/core/status.h"
#include "noisicaa/audioproc/vm/processor_csound_base.h"

namespace noisicaa {

using namespace std;

class HostData;
class ProcessorSpec;

class ProcessorCSound : public ProcessorCSoundBase {
public:
  ProcessorCSound(HostData* host_data);

  Status setup(const ProcessorSpec* spec) override;
  void cleanup() override;
};

}  // namespace noisicaa

#endif
