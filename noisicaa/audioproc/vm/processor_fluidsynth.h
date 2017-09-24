// -*- mode: c++ -*-

#ifndef _NOISICAA_AUDIOPROC_VM_PROCESSOR_FLUIDSYNTH_H
#define _NOISICAA_AUDIOPROC_VM_PROCESSOR_FLUIDSYNTH_H

#include <string>
#include <vector>
#include <stdint.h>
#include "fluidsynth.h"
#include "lv2/lv2plug.in/ns/ext/urid/urid.h"
#include "noisicaa/core/status.h"
#include "noisicaa/audioproc/vm/buffers.h"
#include "noisicaa/audioproc/vm/processor.h"

namespace noisicaa {

using namespace std;

class HostData;
class BlockContext;

class ProcessorFluidSynth : public Processor {
public:
  ProcessorFluidSynth(HostData* host_data);
  ~ProcessorFluidSynth() override;

  Status setup(const ProcessorSpec* spec) override;
  void cleanup() override;

  Status connect_port(uint32_t port_idx, BufferPtr buf) override;
  Status run(BlockContext* ctxt) override;

private:
  BufferPtr _buffers[3];

  fluid_settings_t* _settings = nullptr;
  fluid_synth_t* _synth = nullptr;
};

}  // namespace noisicaa

#endif
