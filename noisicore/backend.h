// -*- mode: c++ -*-

#ifndef _NOISICORE_BACKEND_H
#define _NOISICORE_BACKEND_H

#include <string>
#include "noisicore/status.h"
#include "noisicore/buffers.h"

namespace noisicaa {

using namespace std;

class BlockContext;
class VM;

struct BackendSettings {
  string ipc_address;

  uint32_t block_size;
};

class Backend {
public:
  virtual ~Backend();

  static StatusOr<Backend*> create(const string& name, const BackendSettings& settings);

  virtual Status setup(VM* vm);
  virtual void cleanup();

  virtual Status begin_block(BlockContext* ctxt) = 0;
  virtual Status end_block() = 0;
  virtual Status output(const string& channel, BufferPtr samples) = 0;

protected:
  Backend(const BackendSettings& settings);

  BackendSettings _settings;
  VM* _vm = nullptr;
};

}  // namespace noisicaa

#endif
