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

#ifndef _NOISICAA_HOST_SYSTEM_HOST_SYSTEM_H
#define _NOISICAA_HOST_SYSTEM_HOST_SYSTEM_H

#include <memory>
#include "noisicaa/core/status.h"
#include "noisicaa/host_system/host_system_lv2.h"
#include "noisicaa/host_system/host_system_csound.h"
#include "noisicaa/host_system/host_system_audio_file.h"

namespace noisicaa {

class URIDMapper;

class HostSystem {
public:
  HostSystem(URIDMapper* urid_mapper);
  ~HostSystem();

  Status setup();
  void cleanup();

  uint32_t block_size() const { return _block_size; }
  uint32_t sample_rate() const { return _sample_rate; }

  // Many components assume that block_size and sample_rate remain unchanged for their lifetime.
  // So these values must only be changed, when those components were shutdown.
  void set_block_size(uint32_t block_size) { _block_size = block_size; }
  void set_sample_rate(uint32_t sample_rate) { _sample_rate = sample_rate; }

  unique_ptr<LV2SubSystem> lv2;
  unique_ptr<CSoundSubSystem> csound;
  unique_ptr<AudioFileSubSystem> audio_file;

private:
  uint32_t _block_size = 4096;
  uint32_t _sample_rate = 44100;
};

}  // namespace noisicaa

#endif
