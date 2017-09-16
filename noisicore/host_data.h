// -*- mode: c++ -*-

#ifndef _NOISICORE_HOST_DATA_H
#define _NOISICORE_HOST_DATA_H

#include <memory>
#include "lilv/lilv.h"
#include "lv2/lv2plug.in/ns/ext/urid/urid.h"
#include "noisicore/status.h"

namespace noisicaa {

class LV2SubSystem {
public:
  ~LV2SubSystem();

  Status setup();
  void cleanup();

  LilvWorld* lilv_world = nullptr;

  LV2_URID_Map* urid_map = nullptr;
  LV2_URID_Unmap* urid_unmap = nullptr;

  LV2_URID map(const string& uri);
  string unmap(LV2_URID urid);

  struct {
    LV2_URID midi_event;
    LV2_URID atom_frame_time;
    LV2_URID atom_blank;
    LV2_URID atom_bool;
    LV2_URID atom_chunk;
    LV2_URID atom_double;
    LV2_URID atom_float;
    LV2_URID atom_int;
    LV2_URID atom_long;
    LV2_URID atom_literal;
    LV2_URID atom_object;
    LV2_URID atom_path;
    LV2_URID atom_property;
    LV2_URID atom_resource;
    LV2_URID atom_sequence;
    LV2_URID atom_string;
    LV2_URID atom_tuple;
    LV2_URID atom_uri;
    LV2_URID atom_urid;
    LV2_URID atom_vector;
    LV2_URID atom_event;
  } urid;
};

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
