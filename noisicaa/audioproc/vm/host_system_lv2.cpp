#include <assert.h>
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
    return Status::Error("Failed to create lilv world.");
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

  _features[LV2_URID__map] = bind(&LV2SubSystem::create_map_feature, this, placeholders::_1);
  _features[LV2_URID__unmap] = bind(&LV2SubSystem::create_unmap_feature, this, placeholders::_1);
  // _features[LV2_OPTIONS__options] = nullptr;
  // _features[LV2_BUF_SIZE__boundedBlockLength] = nullptr;
  // _features[LV2_BUF_SIZE__powerOf2BlockLength] = nullptr;
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

bool LV2SubSystem::supports_feature(const char* uri) const {
  return _features.find(uri) != _features.end();
}

void LV2SubSystem::create_feature(const string& uri, LV2_Feature* feature) {
  _features[uri](feature);
}

void LV2SubSystem::create_map_feature(LV2_Feature* feature) {
  feature->URI = LV2_URID__map;
  feature->data = &urid_map;
}

void LV2SubSystem::create_unmap_feature(LV2_Feature* feature) {
  feature->URI = LV2_URID__unmap;
  feature->data = &urid_unmap;
}

}  // namespace noisicaa
