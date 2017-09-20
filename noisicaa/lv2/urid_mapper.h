// -*- mode: c++ -*-

#ifndef _NOISICAA_LV2_URID_MAPPER_H
#define _NOISICAA_LV2_URID_MAPPER_H

#include <map>
#include <unordered_map>
#include <vector>
#include "string.h"
#include "lv2/lv2plug.in/ns/ext/urid/urid.h"

namespace noisicaa {

struct cmp_str;

using namespace std;

class URIDMapper {
public:
  virtual ~URIDMapper() {}

  virtual LV2_URID map(const char* uri) = 0;
  virtual const char* unmap(LV2_URID urid) const = 0;
};

class StaticURIDMapper : public URIDMapper {
public:
  StaticURIDMapper();

  LV2_URID map(const char* uri) override;
  const char* unmap(LV2_URID urid) const override;

private:
  static const LV2_URID _first_urid = 100;
  static const int _num_urids = 21;

  struct cmp_cstr {
    bool operator()(const char *a, const char *b) {
      return strcmp(a, b) < 0;
    }
  };

  std::map<const char*, LV2_URID, cmp_cstr> _map;
  const char* _rmap[_num_urids];
};

class DynamicURIDMapper : public StaticURIDMapper {
public:
  LV2_URID map(const char* uri) override;
  const char* unmap(LV2_URID urid) const override;

private:
  unordered_map<string, LV2_URID> _map;
  unordered_map<LV2_URID, string> _rmap;
  LV2_URID _next_urid = 1000;
};

}  // namespace noisicaa

#endif
