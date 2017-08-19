#ifndef _NOISICORE_BACKEND_H
#define _NOISICORE_BACKEND_H

#include <string>
#include "status.h"
#include "buffers.h"

using std::string;

namespace noisicaa {

class Backend {
 public:
  Backend();
  virtual ~Backend() {};

  static Backend* create(const string& name);

  virtual Status setup() = 0;
  virtual Status cleanup() = 0;

  virtual Status begin_frame() = 0;
  virtual Status end_frame() = 0;
  virtual Status output(const string& channel, BufferPtr samples) = 0;
};

}  // namespace noisicaa

#endif
