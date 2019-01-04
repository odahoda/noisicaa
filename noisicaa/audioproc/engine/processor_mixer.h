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

#ifndef _NOISICAA_AUDIOPROC_ENGINE_PROCESSOR_MIXER_H
#define _NOISICAA_AUDIOPROC_ENGINE_PROCESSOR_MIXER_H

#include <atomic>
#include <memory>

#include "lv2/lv2plug.in/ns/ext/urid/urid.h"

#include "noisicaa/core/status.h"
#include "noisicaa/audioproc/engine/processor_csound_base.h"

namespace noisicaa {

using namespace std;

class HostSystem;

class ProcessorMixer : public ProcessorCSoundBase {
public:
  ProcessorMixer(
      const string& node_id, HostSystem* host_system, const pb::NodeDescription& desc);

protected:
  Status setup_internal() override;
  void cleanup_internal() override;
  Status handle_message_internal(pb::ProcessorMessage* msg) override;
  Status process_block_internal(BlockContext* ctxt, TimeMapper* time_mapper) override;

private:
  LV2_URID _meter_urid;

  atomic<bool> _muted;

  size_t _window_size;
  uint32_t _history_pos;
  unique_ptr<float> _history[2];
  unique_ptr<float> _history_right;
  float _peak_decay;
  uint32_t _peak_hold[2];
  float _peak[2];
};

}  // namespace noisicaa

#endif
