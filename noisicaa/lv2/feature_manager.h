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

#ifndef _NOISICAA_LV2_FEATURE_MANAGER_H
#define _NOISICAA_LV2_FEATURE_MANAGER_H

#include <memory>
#include <string>
#include <vector>
#include "lv2/lv2plug.in/ns/lv2core/lv2.h"
#include "noisicaa/core/status.h"

namespace noisicaa {

class URIDMapper;
class Logger;
class LV2FeatureWrapper;
class HostSystem;

class LV2FeatureManager {
public:
  virtual ~LV2FeatureManager();

  static bool supports_feature(const string& uri);
  LV2_Feature** get_features();

protected:
  LV2FeatureManager(HostSystem* host_system);

  vector<unique_ptr<LV2FeatureWrapper>> _features;

private:
  Logger* _logger;
  HostSystem* _host_system;

  unique_ptr<LV2_Feature*> _feature_array = nullptr;

  static const char* _supported_features[];
};

class LV2PluginFeatureManager : public LV2FeatureManager {
public:
  LV2PluginFeatureManager(HostSystem* host_system);

  static bool supports_feature(const string& uri);

private:
  static const char* _supported_features[];
};

class LV2UIFeatureManager : public LV2FeatureManager {
public:
  LV2UIFeatureManager(HostSystem* host_system, void* parent_widget);

  static bool supports_feature(const string& uri);

private:
  static const char* _supported_features[];
};

}  // namespace noisicaa

#endif
