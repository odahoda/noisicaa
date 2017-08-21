#ifndef _NOISICORE_PROCESSOR_H
#define _NOISICORE_PROCESSOR_H

#include <string>

#include "status.h"
#include "buffers.h"
#include "block_context.h"

using std::string;

namespace noisicaa {

class Processor {
 public:
  Processor();
  virtual ~Processor();

  static Processor* create(const string& name);

  virtual Status setup();
  virtual void cleanup();

  virtual Status connect_port(int port_idx, BufferPtr buf) = 0;
  virtual Status run(BlockContext* ctxt) = 0;
};

}  // namespace noisicaa

#endif
