// -*- mode: c++ -*-

/*
 * @begin:license
 *
 * Copyright (c) 2015-2017, Benjamin Niemann <pink@odahoda.de>
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

#ifndef _NOISICAA_AUDIOPROC_VM_PROCESSOR_CVGENERATOR_H
#define _NOISICAA_AUDIOPROC_VM_PROCESSOR_CVGENERATOR_H

#include <stdint.h>
#include <atomic>
#include <memory>
#include <vector>
#include "noisicaa/core/status.h"
#include "noisicaa/audioproc/vm/buffers.h"
#include "noisicaa/audioproc/vm/musical_time.h"
#include "noisicaa/audioproc/vm/double_buffered_state_manager.h"
#include "noisicaa/audioproc/vm/processor.h"
#include "noisicaa/audioproc/vm/processor_message.pb.h"


namespace noisicaa {

class BlockContext;
class HostData;

class ControlPoint {
public:
  uint64_t id;
  MusicalTime time;
  float value;
};

class CVRecipe : public ManagedState<pb::ProcessorMessage> {
public:
  vector<ControlPoint> control_points;

  int offset = -1;
  MusicalTime current_time = MusicalTime(0, 1);

  void apply_mutation(pb::ProcessorMessage* msg) override;

private:
};

class ProcessorCVGenerator : public Processor {
public:
  ProcessorCVGenerator(const string& node_id, HostData* host_data);
  ~ProcessorCVGenerator() override;

  Status setup(const ProcessorSpec* spec) override;
  void cleanup() override;

  Status connect_port(uint32_t port_idx, BufferPtr buf) override;
  Status run(BlockContext* ctxt, TimeMapper* time_mapper) override;

protected:
  Status handle_message_internal(pb::ProcessorMessage* msg) override;

private:
  BufferPtr _out_buffer;

  DoubleBufferedStateManager<CVRecipe, pb::ProcessorMessage> _recipe_manager;
};

}  // namespace noisicaa

#endif
