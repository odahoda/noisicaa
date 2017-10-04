/*
 * @begin:license
 *
 * Copyright (c) 2015-2017, Benjamin Niemann <pink@odahoda.de>
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

#include <assert.h>
#include <string.h>
#include "lv2/lv2plug.in/ns/ext/urid/urid.h"
#include "lv2/lv2plug.in/ns/ext/options/options.h"
#include "lv2/lv2plug.in/ns/ext/buf-size/buf-size.h"
#include "lv2/lv2plug.in/ns/ext/worker/worker.h"
#include "noisicaa/audioproc/vm/host_system_lv2.h"

namespace noisicaa {

LV2SubSystem::~LV2SubSystem() {
  cleanup();
}

Status LV2SubSystem::setup() {
  assert(lilv_world == nullptr);

  lilv_world = lilv_world_new();
  if (lilv_world == nullptr) {
    return ERROR_STATUS("Failed to create lilv world.");
  }

  lilv_world_load_all(lilv_world);

  urid_map.handle = &_urid_mapper;
  urid_map.map = LV2SubSystem::_urid_map_proxy;
  urid_unmap.handle = &_urid_mapper;
  urid_unmap.unmap = LV2SubSystem::_urid_unmap_proxy;

  urid.midi_event = map("http://lv2plug.in/ns/ext/midi#MidiEvent");
  urid.atom_frame_time = map("http://lv2plug.in/ns/ext/atom#frameTime");
  urid.atom_blank = map("http://lv2plug.in/ns/ext/atom#Blank");
  urid.atom_bool = map("http://lv2plug.in/ns/ext/atom#Bool");
  urid.atom_chunk = map("http://lv2plug.in/ns/ext/atom#Chunk");
  urid.atom_double = map("http://lv2plug.in/ns/ext/atom#Double");
  urid.atom_float = map("http://lv2plug.in/ns/ext/atom#Float");
  urid.atom_int = map("http://lv2plug.in/ns/ext/atom#Int");
  urid.atom_long = map("http://lv2plug.in/ns/ext/atom#Long");
  urid.atom_literal = map("http://lv2plug.in/ns/ext/atom#Literal");
  urid.atom_object = map("http://lv2plug.in/ns/ext/atom#Object");
  urid.atom_path = map("http://lv2plug.in/ns/ext/atom#Path");
  urid.atom_property = map("http://lv2plug.in/ns/ext/atom#Property");
  urid.atom_resource = map("http://lv2plug.in/ns/ext/atom#Resource");
  urid.atom_sequence = map("http://lv2plug.in/ns/ext/atom#Sequence");
  urid.atom_string = map("http://lv2plug.in/ns/ext/atom#String");
  urid.atom_tuple = map("http://lv2plug.in/ns/ext/atom#Tuple");
  urid.atom_uri = map("http://lv2plug.in/ns/ext/atom#URI");
  urid.atom_urid = map("http://lv2plug.in/ns/ext/atom#URID");
  urid.atom_vector = map("http://lv2plug.in/ns/ext/atom#Vector");
  urid.atom_event = map("http://lv2plug.in/ns/ext/atom#Event");

  _features.emplace_back(
      Feature {
        LV2_URID__map,
        bind(&LV2SubSystem::create_map_feature, this, placeholders::_1),
        nullptr
      });
  _features.emplace_back(
      Feature {
        LV2_URID__unmap,
        bind(&LV2SubSystem::create_unmap_feature, this, placeholders::_1),
        nullptr
      });
  _features.emplace_back(
      Feature {
        LV2_OPTIONS__options,
        bind(&LV2SubSystem::create_options_feature, this, placeholders::_1),
        bind(&LV2SubSystem::delete_options_feature, this, placeholders::_1)
      });
  _features.emplace_back(
      Feature {
        LV2_BUF_SIZE__boundedBlockLength,
        nullptr,
        nullptr
      });
  _features.emplace_back(
      Feature {
        LV2_BUF_SIZE__powerOf2BlockLength,
        nullptr,
        nullptr
      });
  // _features[LV2_WORKER__schedule] = nullptr;

  return Status::Ok();
}

void LV2SubSystem::cleanup() {
  if (lilv_world != nullptr) {
    lilv_world_free(lilv_world);
    lilv_world = nullptr;
  }
}

LV2_URID LV2SubSystem::_urid_map_proxy(LV2_URID_Map_Handle handle, const char* uri) {
  return ((URIDMapper*)handle)->map(uri);
}

const char* LV2SubSystem::_urid_unmap_proxy(LV2_URID_Unmap_Handle handle, LV2_URID urid) {
  return ((URIDMapper*)handle)->unmap(urid);
}

bool LV2SubSystem::supports_feature(const string& uri) const {
  for (const auto& feature : _features) {
    if (feature.uri == uri) {
      return true;
    }
  }

  return false;
}

LV2_Feature* LV2SubSystem::create_feature(const string& uri) {
  for (const auto& f : _features) {
    if (f.uri == uri) {
      LV2_Feature* feature = new LV2_Feature;
      feature->URI = f.uri.c_str();
      if (f.create_func != nullptr) {
        f.create_func(feature);
      } else {
        feature->data = nullptr;
      }
      return feature;
    }
  }

  return nullptr;
}

void LV2SubSystem::delete_feature(LV2_Feature* feature) {
  string uri = feature->URI;
  for (const auto& f : _features) {
    if (f.uri == uri) {
      if (f.delete_func != nullptr) {
        f.delete_func(feature);
      }
      delete feature;
      return;
    }
  }

  assert(false);
}

void LV2SubSystem::create_map_feature(LV2_Feature* feature) {
  feature->data = &urid_map;
}

void LV2SubSystem::create_unmap_feature(LV2_Feature* feature) {
  feature->data = &urid_unmap;
}

void LV2SubSystem::create_options_feature(LV2_Feature* feature) {
  LV2_Options_Option* options = new LV2_Options_Option[5];

  options[0].context = LV2_OPTIONS_INSTANCE;
  options[0].subject = 0;
  options[0].key = map("http://lv2plug.in/ns/ext/parameters#sampleRate");
  options[0].size = sizeof(float);
  options[0].type = urid.atom_float;
  options[0].value = &_sample_rate;

  options[1].context = LV2_OPTIONS_INSTANCE;
  options[1].subject = 0;
  options[1].key = map(LV2_BUF_SIZE__minBlockLength);
  options[1].size = sizeof(int32_t);
  options[1].type = urid.atom_int;
  options[1].value = &_min_block_size;

  options[2].context = LV2_OPTIONS_INSTANCE;
  options[2].subject = 0;
  options[2].key = map(LV2_BUF_SIZE__maxBlockLength);
  options[2].size = sizeof(int32_t);
  options[2].type = urid.atom_int;
  options[2].value = &_max_block_size;

  options[3].context = LV2_OPTIONS_INSTANCE;
  options[3].subject = 0;
  options[3].key = map(LV2_BUF_SIZE__sequenceSize);
  options[3].size = sizeof(int32_t);
  options[3].type = urid.atom_int;
  options[3].value = &_atom_data_size;

  options[4].context = LV2_OPTIONS_INSTANCE;
  options[4].subject = 0;
  options[4].key = 0;
  options[4].size = 0;
  options[4].type = 0;
  options[4].value = nullptr;

  feature->data = options;
}

void LV2SubSystem::delete_options_feature(LV2_Feature* feature) {
  LV2_Options_Option* options = (LV2_Options_Option*)feature->data;
  delete options;
}

}  // namespace noisicaa
