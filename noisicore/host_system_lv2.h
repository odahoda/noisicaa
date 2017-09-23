// -*- mode: c++ -*-

#ifndef _NOISICORE_HOST_SYSTEM_LV2_H
#define _NOISICORE_HOST_SYSTEM_LV2_H

#include <unordered_map>
#include "lilv/lilv.h"
#include "lv2/lv2plug.in/ns/ext/urid/urid.h"
#include "noisicaa/core/status.h"
#include "noisicaa/lv2/urid_mapper.h"

namespace noisicaa {

class LV2SubSystem {
public:
  ~LV2SubSystem();

  Status setup();
  void cleanup();

  LilvWorld* lilv_world = nullptr;

  LV2_URID_Map urid_map = { nullptr, nullptr };
  LV2_URID_Unmap urid_unmap = { nullptr, nullptr };

  LV2_URID map(const char* uri) { return _urid_mapper.map(uri); }
  const char* unmap(LV2_URID urid) { return _urid_mapper.unmap(urid); }

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

private:
  DynamicURIDMapper _urid_mapper;

  static LV2_URID _urid_map_proxy(LV2_URID_Map_Handle handle, const char* uri);
  static const char* _urid_unmap_proxy(LV2_URID_Unmap_Handle handle, LV2_URID urid);
};

}  // namespace noisicaa

#endif
