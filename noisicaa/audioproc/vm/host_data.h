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

#ifndef _NOISICAA_AUDIOPROC_VM_HOST_DATA_H
#define _NOISICAA_AUDIOPROC_VM_HOST_DATA_H

#include <memory>
#include "noisicaa/core/status.h"
#include "noisicaa/audioproc/vm/host_system_lv2.h"
#include "noisicaa/audioproc/vm/host_system_csound.h"
#include "noisicaa/audioproc/vm/host_system_audio_file.h"

namespace noisicaa {

class HostData {
public:
  HostData();
  ~HostData();

  Status setup();
  void cleanup();

  unique_ptr<LV2SubSystem> lv2;
  unique_ptr<CSoundSubSystem> csound;
  unique_ptr<AudioFileSubSystem> audio_file;
};

}  // namespace noisicaa

#endif
