#include <assert.h>
#include "noisicore/host_data.h"

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

  return Status::Ok();
}

void LV2SubSystem::cleanup() {
  if (lilv_world != nullptr) {
    lilv_world_free(lilv_world);
    lilv_world = nullptr;
  }
}

LV2_URID LV2SubSystem::map(const string& uri) {
  return urid_map->map(urid_map->handle, uri.c_str());
}

string LV2SubSystem::unmap(LV2_URID urid) {
  return urid_unmap->unmap(urid_unmap->handle, urid);
}

HostData::HostData()
  : lv2(new LV2SubSystem()) {}

HostData::~HostData() {
  cleanup();
}

Status HostData::setup() {
  Status status;

  status = lv2->setup();
  if (status.is_error()) { return status; }

  return Status::Ok();
}

void HostData::cleanup() {
  lv2->cleanup();
}

}  // namespace noisicaa
