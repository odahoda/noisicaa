// -*- mode: c++ -*-

#ifndef _NOISICAA_AUDIOPROC_VM_PROCESSOR_CUSTOM_CSOUND_H
#define _NOISICAA_AUDIOPROC_VM_PROCESSOR_CUSTOM_CSOUND_H

#include "noisicaa/audioproc/vm/processor_csound_base.h"

namespace noisicaa {

using namespace std;

class HostData;
class ProcessorSpec;

class ProcessorCustomCSound : public ProcessorCSoundBase {
public:
  ProcessorCustomCSound(const string& node_id, HostData* host_data);

  Status setup(const ProcessorSpec* spec) override;
  void cleanup() override;
};

}  // namespace noisicaa

#endif
