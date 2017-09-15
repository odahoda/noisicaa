// -*- mode: c++ -*-

#ifndef _NOISICORE_BACKEND_NULL_H
#define _NOISICORE_BACKEND_NULL_H

#include <string.h>
#include "noisicore/backend.h"
#include "noisicore/buffers.h"
#include "noisicore/status.h"

namespace noisicaa {

class VM;

class NullBackend : public Backend {
 public:
  NullBackend(const BackendSettings& settings);
  ~NullBackend() override;

  Status setup(VM* vm) override;
  void cleanup() override;

  Status begin_block(BlockContext* ctxt) override;
  Status end_block() override;
  Status output(const string& channel, BufferPtr samples) override;
};

}  // namespace noisicaa

#endif
