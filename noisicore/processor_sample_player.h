// -*- mode: c++ -*-

#ifndef _NOISICORE_PROCESSOR_SAMPLE_PLAYER_H
#define _NOISICORE_PROCESSOR_SAMPLE_PLAYER_H

#include "noisicore/status.h"
#include "noisicore/processor_csound_base.h"

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
