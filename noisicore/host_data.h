#ifndef _NOISICORE_HOST_DATA_H
#define _NOISICORE_HOST_DATA_H

#include "lilv/lilv.h"

#include "status.h"

using namespace std;

namespace noisicaa {

class HostData {
 public:
  ~HostData();

  Status setup();
  Status setup_lilv();

  void cleanup();

  LilvWorld* lilv_world = nullptr;
};

}  // namespace noisicaa

#endif
