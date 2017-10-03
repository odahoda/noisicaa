// -*- mode: c++ -*-

#ifndef _NOISICAA_AUDIOPROC_VM_PROCESSOR_SOUND_FILE_H
#define _NOISICAA_AUDIOPROC_VM_PROCESSOR_SOUND_FILE_H

#include <string>
#include <vector>
#include <stdint.h>
#include "noisicaa/core/status.h"
#include "noisicaa/audioproc/vm/buffers.h"
#include "noisicaa/audioproc/vm/processor.h"

namespace noisicaa {

using namespace std;

class HostData;
class BlockContext;

class ProcessorSoundFile : public Processor {
public:
  ProcessorSoundFile(const string& node_id, HostData* host_data);
  ~ProcessorSoundFile() override;

  Status setup(const ProcessorSpec* spec) override;
  void cleanup() override;

  Status connect_port(uint32_t port_idx, BufferPtr buf) override;
  Status run(BlockContext* ctxt) override;

private:
  unique_ptr<float> _left_samples;
  unique_ptr<float> _right_samples;
  bool _loop;
  bool _playing;
  uint32_t _pos;
  uint32_t _num_samples;
  BufferPtr _buf[2];
};

}  // namespace noisicaa

#endif
