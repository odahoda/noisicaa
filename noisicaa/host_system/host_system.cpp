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

#include <assert.h>
#include "noisicaa/host_system/host_system.h"

namespace noisicaa {

HostSystem::HostSystem(URIDMapper* urid_mapper)
  : lv2(new LV2SubSystem(urid_mapper)),
    csound(new CSoundSubSystem()),
    audio_file(new AudioFileSubSystem()) {}

HostSystem::~HostSystem() {
  cleanup();
}

Status HostSystem::setup() {
  RETURN_IF_ERROR(lv2->setup());
  RETURN_IF_ERROR(csound->setup());
  RETURN_IF_ERROR(audio_file->setup(_sample_rate));
  return Status::Ok();
}

void HostSystem::cleanup() {
  audio_file->cleanup();
  csound->cleanup();
  lv2->cleanup();
}

}  // namespace noisicaa
