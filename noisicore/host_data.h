// -*- mode: c++ -*-

#ifndef _NOISICORE_HOST_DATA_H
#define _NOISICORE_HOST_DATA_H

#include <memory>
#include "noisicore/host_system_lv2.h"
#include "noisicore/status.h"

namespace noisicaa {

class HostData {
public:
  HostData();
  ~HostData();

  Status setup();
  void cleanup();

  unique_ptr<LV2SubSystem> lv2;
};

}  // namespace noisicaa

#endif
