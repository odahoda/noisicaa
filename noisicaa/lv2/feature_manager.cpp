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

#include <assert.h>
#include "lv2/lv2plug.in/ns/ext/urid/urid.h"
#include "lv2/lv2plug.in/ns/ext/options/options.h"
#include "lv2/lv2plug.in/ns/ext/buf-size/buf-size.h"
#include "lv2/lv2plug.in/ns/ext/worker/worker.h"
#include "lv2/lv2plug.in/ns/ext/instance-access/instance-access.h"
#include "lv2/lv2plug.in/ns/extensions/ui/ui.h"
#include "noisicaa/core/logging.h"
#include "noisicaa/host_system/host_system.h"
#include "noisicaa/lv2/urid_mapper.h"
#include "noisicaa/lv2/feature_manager.h"

#define LV2_UI__makeResident LV2_UI_PREFIX "makeResident"

namespace noisicaa {

class LV2FeatureWrapper {
public:
  LV2FeatureWrapper(const char* uri, void* data)
    : _uri(uri), _data(data) {}

  virtual ~LV2FeatureWrapper() {}

  const char* uri() const { return _uri.c_str(); }
  void *data() const { return _data; }

private:
  string _uri;
  void* _data;
};

namespace lv2_feature_wrapper {

class Map : public LV2FeatureWrapper {
public:
  Map(URIDMapper* urid_mapper)
    : LV2FeatureWrapper(LV2_URID__map, &_urid_map) {
  _urid_map.handle = urid_mapper;
  _urid_map.map = Map::_urid_map_proxy;
  }

private:
  LV2_URID_Map _urid_map = { nullptr, nullptr };

  static LV2_URID _urid_map_proxy(LV2_URID_Map_Handle handle, const char* uri) {
    return ((URIDMapper*)handle)->map(uri);
  }
};

class Unmap : public LV2FeatureWrapper {
public:
  Unmap(URIDMapper* urid_mapper)
    : LV2FeatureWrapper(LV2_URID__unmap, &_urid_unmap) {
  _urid_unmap.handle = urid_mapper;
  _urid_unmap.unmap = Unmap::_urid_unmap_proxy;
  }

private:
  LV2_URID_Unmap _urid_unmap = { nullptr, nullptr };

  static const char* _urid_unmap_proxy(LV2_URID_Unmap_Handle handle, LV2_URID urid) {
    return ((URIDMapper*)handle)->unmap(urid);
  }
};

class Options : public LV2FeatureWrapper {
public:
  Options(HostSystem* host_system)
    : LV2FeatureWrapper(LV2_OPTIONS__options, _options),
      _sample_rate(host_system->sample_rate()),
      _block_size(host_system->block_size()) {
    URIDMapper* mapper = host_system->lv2->urid_mapper();

    _options[0].context = LV2_OPTIONS_INSTANCE;
    _options[0].subject = 0;
    _options[0].key = mapper->map("http://lv2plug.in/ns/ext/parameters#sampleRate");
    _options[0].size = sizeof(float);
    _options[0].type = mapper->map("http://lv2plug.in/ns/ext/atom#Float");
    _options[0].value = &_sample_rate;

    _options[1].context = LV2_OPTIONS_INSTANCE;
    _options[1].subject = 0;
    _options[1].key = mapper->map(LV2_BUF_SIZE__minBlockLength);
    _options[1].size = sizeof(int32_t);
    _options[1].type = mapper->map("http://lv2plug.in/ns/ext/atom#Int");
    _options[1].value = &_block_size;

    _options[2].context = LV2_OPTIONS_INSTANCE;
    _options[2].subject = 0;
    _options[2].key = mapper->map(LV2_BUF_SIZE__maxBlockLength);
    _options[2].size = sizeof(int32_t);
    _options[2].type = mapper->map("http://lv2plug.in/ns/ext/atom#Int");
    _options[2].value = &_block_size;

    _options[3].context = LV2_OPTIONS_INSTANCE;
    _options[3].subject = 0;
    _options[3].key = mapper->map(LV2_BUF_SIZE__sequenceSize);
    _options[3].size = sizeof(int32_t);
    _options[3].type = mapper->map("http://lv2plug.in/ns/ext/atom#Int");
    _options[3].value = &_atom_data_size;

    _options[4].context = LV2_OPTIONS_INSTANCE;
    _options[4].subject = 0;
    _options[4].key = 0;
    _options[4].size = 0;
    _options[4].type = 0;
    _options[4].value = nullptr;
  }

private:
  LV2_Options_Option _options[5];

  float _sample_rate;
  int32_t _block_size;
  int32_t _atom_data_size = 10240;
};

class BoundedBlockLength : public LV2FeatureWrapper {
public:
  BoundedBlockLength()
    : LV2FeatureWrapper(LV2_BUF_SIZE__boundedBlockLength, nullptr) {}
};

class PowerOf2BlockLength : public LV2FeatureWrapper {
public:
  PowerOf2BlockLength()
    : LV2FeatureWrapper(LV2_BUF_SIZE__powerOf2BlockLength, nullptr) {}
};

class FixedBlockLength : public LV2FeatureWrapper {
public:
  FixedBlockLength()
    : LV2FeatureWrapper(LV2_BUF_SIZE__fixedBlockLength, nullptr) {}
};

class ParentWidget : public LV2FeatureWrapper {
public:
  ParentWidget(void* parent_widget)
    : LV2FeatureWrapper(LV2_UI__parent, parent_widget) {}
};

class InstanceAccess : public LV2FeatureWrapper {
public:
  InstanceAccess(void* instance)
    : LV2FeatureWrapper(LV2_INSTANCE_ACCESS_URI, instance) {}
};

class MakeResident : public LV2FeatureWrapper {
public:
  MakeResident()
    : LV2FeatureWrapper(LV2_UI__makeResident, nullptr) {}
};

}  // namespace lv2_feature_wrapper

const char* LV2FeatureManager::_supported_features[] = {
  LV2_URID__map,
  LV2_URID__unmap,
  LV2_OPTIONS__options,
  LV2_BUF_SIZE__boundedBlockLength,
  LV2_BUF_SIZE__powerOf2BlockLength,
  LV2_BUF_SIZE__fixedBlockLength,
  nullptr
};

LV2FeatureManager::LV2FeatureManager(HostSystem* host_system)
  : _logger(LoggerRegistry::get_logger("noisicaa.lv2.feature_manager")),
    _host_system(host_system) {
  URIDMapper* urid_mapper = host_system->lv2->urid_mapper();

  _features.emplace_back(new lv2_feature_wrapper::Map(urid_mapper));
  _features.emplace_back(new lv2_feature_wrapper::Unmap(urid_mapper));
  _features.emplace_back(new lv2_feature_wrapper::Options(_host_system));
  _features.emplace_back(new lv2_feature_wrapper::BoundedBlockLength());
  _features.emplace_back(new lv2_feature_wrapper::PowerOf2BlockLength());
  _features.emplace_back(new lv2_feature_wrapper::FixedBlockLength());

  for (const char** sfeature = _supported_features ; *sfeature ; ++sfeature) {
    bool found = false;
    for (const auto& afeature : _features) {
      if (strcmp(afeature->uri(), *sfeature) == 0) {
        found = true;
      }
    }
    assert(found);
  }
}

LV2FeatureManager::~LV2FeatureManager() {
  if (_feature_array.get() != nullptr) {
    for (LV2_Feature** it = _feature_array.get() ; *it ; ++it) {
      delete *it;
    }
  }
}

LV2_Feature** LV2FeatureManager::get_features() {
  if (_feature_array.get() == nullptr) {
    _feature_array.reset(new LV2_Feature*[_features.size() + 1]);

    LV2_Feature** it = _feature_array.get();
    for (const auto& feature : _features) {
      *it = new LV2_Feature;
      (*it)->URI = feature->uri();
      (*it)->data = feature->data();
      ++it;
    }
    *it = nullptr;
  }

  return _feature_array.get();
}

bool LV2FeatureManager::supports_feature(const string& uri) {
  for (const char** feature = _supported_features ; *feature ; ++feature) {
    if (strcmp(uri.c_str(), *feature) == 0) {
      return true;
    }
  }

  return false;
}

const char* LV2PluginFeatureManager::_supported_features[] = {
  nullptr
};

LV2PluginFeatureManager::LV2PluginFeatureManager(HostSystem* host_system)
  : LV2FeatureManager(host_system) {
}

bool LV2PluginFeatureManager::supports_feature(const string& uri) {
  if (LV2FeatureManager::supports_feature(uri)) {
    return true;
  }

  for (const char** feature = _supported_features ; *feature ; ++feature) {
    if (strcmp(uri.c_str(), *feature) == 0) {
      return true;
    }
  }

  return false;
}

const char* LV2UIFeatureManager::_supported_features[] = {
  LV2_UI__parent,
  LV2_UI__makeResident,
  LV2_INSTANCE_ACCESS_URI,

  // These features are implicitly added by suil:
  LV2_UI__portMap,
  LV2_UI__portSubscribe,
  LV2_UI__touch,
  LV2_UI__resize,

  nullptr
};

LV2UIFeatureManager::LV2UIFeatureManager(HostSystem* host_system, void* parent_widget, void* instance)
  : LV2FeatureManager(host_system) {
  _features.emplace_back(new lv2_feature_wrapper::ParentWidget(parent_widget));
  _features.emplace_back(new lv2_feature_wrapper::MakeResident());
  _features.emplace_back(new lv2_feature_wrapper::InstanceAccess(instance));
}

bool LV2UIFeatureManager::supports_feature(const string& uri) {
  if (LV2FeatureManager::supports_feature(uri)) {
    return true;
  }

  for (const char** feature = _supported_features ; *feature ; ++feature) {
    if (strcmp(uri.c_str(), *feature) == 0) {
      return true;
    }
  }

  return false;
}

}  // namespace noisicaa
