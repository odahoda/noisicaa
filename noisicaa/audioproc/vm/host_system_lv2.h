// -*- mode: c++ -*-

/*
 * @begin:license
 *
 * Copyright (c) 2015-2018, Benjamin Niemann <pink@odahoda.de>
 *
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation; either version 2 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License along
 * with this program; if not, write to the Free Software Foundation, Inc.,
 * 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
 *
 * @end:license
 */

#ifndef _NOISICAA_AUDIOPROC_VM_HOST_SYSTEM_LV2_H
#define _NOISICAA_AUDIOPROC_VM_HOST_SYSTEM_LV2_H

#include <functional>
#include <map>
#include <string>
#include "lilv/lilv.h"
#include "lv2/lv2plug.in/ns/lv2core/lv2.h"
#include "lv2/lv2plug.in/ns/ext/urid/urid.h"
#include "noisicaa/core/status.h"
#include "noisicaa/lv2/urid_mapper.h"

namespace noisicaa {

using namespace std;

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

  bool supports_feature(const string& uri) const;
  LV2_Feature* create_feature(const string& uri);
  void delete_feature(LV2_Feature* feature);

private:
  DynamicURIDMapper _urid_mapper;

  static LV2_URID _urid_map_proxy(LV2_URID_Map_Handle handle, const char* uri);
  static const char* _urid_unmap_proxy(LV2_URID_Unmap_Handle handle, LV2_URID urid);

  float _sample_rate = 44100;
  int32_t _min_block_size = 32;
  int32_t _max_block_size = 2<<16;
  int32_t _atom_data_size = 10240;

  struct Feature {
    string uri;
    function<void(LV2_Feature*)> create_func;
    function<void(LV2_Feature*)> delete_func;
  };
  vector<Feature> _features;

  void create_map_feature(LV2_Feature*);
  void create_unmap_feature(LV2_Feature*);
  void create_options_feature(LV2_Feature*);
  void delete_options_feature(LV2_Feature*);
};

}  // namespace noisicaa

#endif
