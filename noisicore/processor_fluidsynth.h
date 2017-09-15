// -*- mode: c++ -*-

#ifndef _NOISICORE_PROCESSOR_FLUIDSYNTH_H
#define _NOISICORE_PROCESSOR_FLUIDSYNTH_H

#include <string>
#include <vector>
#include <stdint.h>
#include "fluidsynth.h"
#include "lv2/lv2plug.in/ns/ext/urid/urid.h"
#include "noisicore/status.h"
#include "noisicore/buffers.h"
#include "noisicore/processor.h"

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
  LV2_URID _sequence_urid;
  LV2_URID _midi_event_urid;
};

}  // namespace noisicaa

#endif
