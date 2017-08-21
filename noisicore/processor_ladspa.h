#ifndef _NOISICORE_PROCESSOR_LADSPA_H
#define _NOISICORE_PROCESSOR_LADSPA_H

#include <string>
#include <vector>
#include "ladspa.h"

#include "status.h"
#include "buffers.h"
#include "block_context.h"
#include "processor.h"

using std::string;
using std::vector;

namespace noisicaa {

class ProcessorLadspa : public Processor {
 public:
  ProcessorLadspa();
  ~ProcessorLadspa() override;

  Status setup() override;
  void cleanup() override;

  Status connect_port(int port_idx, BufferPtr buf) override;
  Status run(BlockContext* ctxt) override;

 private:
  void* _library;
  const LADSPA_Descriptor*_descriptor;
  LADSPA_Handle _instance;
};

}  // namespace noisicaa

#endif
