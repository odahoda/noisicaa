#ifndef _NOISICORE_BACKEND_H
#define _NOISICORE_BACKEND_H

#include <string>
#include "status.h"
#include "buffers.h"

namespace noisicaa {

using namespace std;

class VM;

class Backend {
 public:
  Backend();
  virtual ~Backend() {};

  static Backend* create(const string& name);

  virtual Status setup(VM* vm);
  virtual void cleanup() = 0;

  virtual Status begin_block() = 0;
  virtual Status end_block() = 0;
  virtual Status output(const string& channel, BufferPtr samples) = 0;

 protected:
  VM* _vm;
};

}  // namespace noisicaa

#endif
