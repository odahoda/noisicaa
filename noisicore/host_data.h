// -*- mode: c++ -*-

#ifndef _NOISICORE_HOST_DATA_H
#define _NOISICORE_HOST_DATA_H

#include "lilv/lilv.h"
#include "lv2/lv2plug.in/ns/ext/urid/urid.h"

#include "status.h"

namespace noisicaa {

class HostData {
public:
  ~HostData();

  Status setup();
  Status setup_lilv();
  Status setup_lv2();

  void cleanup();

  LilvWorld* lilv_world = nullptr;

  LV2_URID_Map* lv2_urid_map = nullptr;
  LV2_URID_Unmap* lv2_urid_unmap = nullptr;
};

}  // namespace noisicaa

#endif
