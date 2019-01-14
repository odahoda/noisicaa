// -*- mode: c++ -*-

/*
 * @begin:license
 *
 * Copyright (c) 2015-2019, Benjamin Niemann <pink@odahoda.de>
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

#ifndef _NOISICAA_AUDIOPROC_ENGINE_ALSA_DEVICE_MANAGER_H
#define _NOISICAA_AUDIOPROC_ENGINE_ALSA_DEVICE_MANAGER_H

#include <map>
#include <string>
#include "alsa/asoundlib.h"
#include "noisicaa/core/slots.h"
#include "noisicaa/core/status.h"

namespace noisicaa {

class Logger;
namespace pb {
class EngineNotification;
class DeviceDescription;
}

class ALSADeviceManager {
public:
  ALSADeviceManager(
      int client_id,
      Slot<pb::EngineNotification>& notifications);
  ~ALSADeviceManager();

  Status setup();
  void process_events();

private:
  StatusOr<pb::DeviceDescription> get_device_description(int client_id);
  void add_device(const pb::DeviceDescription& device);
  void update_device(const pb::DeviceDescription& device);
  void remove_device(const pb::DeviceDescription& device);

private:
  Logger* _logger;
  int _client_id;
  Slot<pb::EngineNotification>& _notifications;
  snd_seq_t* _seq = nullptr;
  map<string, pb::DeviceDescription> _devices;
};

}  // namespace noisicaa

#endif
