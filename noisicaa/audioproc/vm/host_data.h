// -*- mode: c++ -*-

#ifndef _NOISICAA_AUDIOPROC_VM_HOST_DATA_H
#define _NOISICAA_AUDIOPROC_VM_HOST_DATA_H

#include <memory>
#include "noisicaa/core/status.h"
#include "noisicaa/audioproc/vm/host_system_lv2.h"
#include "noisicaa/audioproc/vm/host_system_csound.h"

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
