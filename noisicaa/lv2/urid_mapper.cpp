#include <assert.h>
#include "noisicaa/lv2/urid_mapper.h"

namespace noisicaa {

StaticURIDMapper::StaticURIDMapper() {
  LV2_URID urid = 0;
  _rmap[urid++] = "http://lv2plug.in/ns/ext/midi#MidiEvent";
  _rmap[urid++] = "http://lv2plug.in/ns/ext/atom#frameTime";
  _rmap[urid++] = "http://lv2plug.in/ns/ext/atom#Blank";
  _rmap[urid++] = "http://lv2plug.in/ns/ext/atom#Bool";
  _rmap[urid++] = "http://lv2plug.in/ns/ext/atom#Chunk";
  _rmap[urid++] = "http://lv2plug.in/ns/ext/atom#Double";
  _rmap[urid++] = "http://lv2plug.in/ns/ext/atom#Float";
  _rmap[urid++] = "http://lv2plug.in/ns/ext/atom#Int";
  _rmap[urid++] = "http://lv2plug.in/ns/ext/atom#Long";
  _rmap[urid++] = "http://lv2plug.in/ns/ext/atom#Literal";
  _rmap[urid++] = "http://lv2plug.in/ns/ext/atom#Object";
  _rmap[urid++] = "http://lv2plug.in/ns/ext/atom#Path";
  _rmap[urid++] = "http://lv2plug.in/ns/ext/atom#Property";
  _rmap[urid++] = "http://lv2plug.in/ns/ext/atom#Resource";
  _rmap[urid++] = "http://lv2plug.in/ns/ext/atom#Sequence";
  _rmap[urid++] = "http://lv2plug.in/ns/ext/atom#String";
  _rmap[urid++] = "http://lv2plug.in/ns/ext/atom#Tuple";
  _rmap[urid++] = "http://lv2plug.in/ns/ext/atom#URI";
  _rmap[urid++] = "http://lv2plug.in/ns/ext/atom#URID";
  _rmap[urid++] = "http://lv2plug.in/ns/ext/atom#Vector";
  _rmap[urid++] = "http://lv2plug.in/ns/ext/atom#Event";
  _rmap[urid++] = "http://lv2plug.in/ns/ext/parameters#sampleRate";
  _rmap[urid++] = "http://lv2plug.in/ns/ext/buf-size#minBlockLength";
  _rmap[urid++] = "http://lv2plug.in/ns/ext/buf-size#maxBlockLength";
  _rmap[urid++] = "http://lv2plug.in/ns/ext/buf-size#sequenceSize";
  assert(urid == _num_urids);

  urid = _first_urid;
  for (const auto& uri : _rmap) {
    _map[uri] = urid++;
  }
}

LV2_URID StaticURIDMapper::map(const char* uri) {
  const auto& it = _map.find(uri);
  if (it == _map.end()) {
    return 0;
  }
  return it->second;
}

const char* StaticURIDMapper::unmap(LV2_URID urid) const {
  if (urid < _first_urid || urid >= _first_urid + _num_urids) {
    return nullptr;
  }

  return _rmap[urid - _first_urid];
}


LV2_URID DynamicURIDMapper::map(const char* uri) {
  LV2_URID urid = StaticURIDMapper::map(uri);
  if (urid != 0) {
    return urid;
  }

  const auto& it = _map.find(uri);
  if (it == _map.end()) {
    urid = _next_urid++;
    _map.emplace(uri, urid);
    _rmap.emplace(urid, uri);
    return urid;
  }
  return it->second;
}

const char* DynamicURIDMapper::unmap(LV2_URID urid) const {
  const char* uri = StaticURIDMapper::unmap(urid);
  if (uri != nullptr) {
    return uri;
  }

  const auto& it = _rmap.find(urid);
  if (it == _rmap.end()) {
    return nullptr;
  }
  return it->second.c_str();
}

}  // namespace noisicaa
