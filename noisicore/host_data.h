// -*- mode: c++ -*-

#ifndef _NOISICORE_HOST_DATA_H
#define _NOISICORE_HOST_DATA_H

#include <memory>
#include "noisicaa/core/status.h"
#include "noisicore/host_system_lv2.h"
#include "noisicore/host_system_csound.h"

namespace noisicaa {

class HostData {
public:
  HostData();
  ~HostData();

  Status setup();
  void cleanup();

  unique_ptr<LV2SubSystem> lv2;
  unique_ptr<CSoundSubSystem> csound;
};

}  // namespace noisicaa

#endif
