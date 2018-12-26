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

#ifndef _NOISICAA_LV2_URID_MAPPER_H
#define _NOISICAA_LV2_URID_MAPPER_H

#include <map>
#include <string>
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
  static const int _num_urids = 26;

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

  bool known(const char* uri) const { return _map.count(uri) > 0; }

  typedef unordered_map<string, LV2_URID>::const_iterator const_iterator;
  const_iterator begin() const { return _map.begin(); }
  const_iterator end() const { return _map.end(); }

private:
  unordered_map<string, LV2_URID> _map;
  unordered_map<LV2_URID, string> _rmap;
  LV2_URID _next_urid = 1000;
};

class ProxyURIDMapper : public StaticURIDMapper {
public:
  ProxyURIDMapper(LV2_URID (*map_func)(void*, const char*), void* handle);

  LV2_URID map(const char* uri) override;
  const char* unmap(LV2_URID urid) const override;

  void insert(const char*uri, LV2_URID urid);

private:
  LV2_URID (*_map_func)(void*, const char*);
  void* _handle;

  unordered_map<string, LV2_URID> _map;
  unordered_map<LV2_URID, string> _rmap;
};

}  // namespace noisicaa

#endif
