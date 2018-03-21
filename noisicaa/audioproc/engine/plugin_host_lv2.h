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

#ifndef _NOISICAA_AUDIOPROC_ENGINE_PLUGIN_HOST_LV2_H
#define _NOISICAA_AUDIOPROC_ENGINE_PLUGIN_HOST_LV2_H

#include <memory>
#include "lilv/lilv.h"
#include "noisicaa/core/status.h"
#include "noisicaa/audioproc/engine/plugin_host.h"

namespace noisicaa {

using namespace std;

class LV2PluginFeatureManager;

class PluginHostLV2 : public PluginHost {
public:
  PluginHostLV2(const pb::PluginInstanceSpec& spec, HostSystem* host_system);
  ~PluginHostLV2() override;

  Status setup() override;
  void cleanup() override;

  Status connect_port(uint32_t port_idx, BufferPtr buf) override;
  Status process_block(uint32_t block_size) override;

private:
  unique_ptr<LV2PluginFeatureManager> _feature_manager;
  const LilvPlugin* _plugin = nullptr;
  LilvInstance* _instance = nullptr;
};

}  // namespace noisicaa

#endif
