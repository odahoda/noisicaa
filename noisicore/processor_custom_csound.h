// -*- mode: c++ -*-

#ifndef _NOISICORE_PROCESSOR_CUSTOM_CSOUND_H
#define _NOISICORE_PROCESSOR_CUSTOM_CSOUND_H

#include "noisicore/processor_csound_base.h"

namespace noisicaa {

using namespace std;

class HostData;
class ProcessorSpec;

class ProcessorCustomCSound : public ProcessorCSoundBase {
public:
  ProcessorCustomCSound(HostData* host_data);

  Status setup(const ProcessorSpec* spec) override;
  void cleanup() override;
};

}  // namespace noisicaa

#endif
