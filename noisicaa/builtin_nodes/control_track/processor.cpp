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

#include <algorithm>

#include "noisicaa/core/perf_stats.h"
#include "noisicaa/audioproc/public/processor_message.pb.h"
#include "noisicaa/audioproc/engine/misc.h"
#include "noisicaa/host_system/host_system.h"
#include "noisicaa/audioproc/engine/double_buffered_state_manager.inl.h"
#include "noisicaa/builtin_nodes/processor_message_registry.pb.h"
#include "noisicaa/builtin_nodes/control_track/processor_messages.pb.h"
#include "noisicaa/builtin_nodes/control_track/processor.h"

namespace {

using namespace std;
using namespace noisicaa;

bool control_point_comp(const ControlPoint &e1, const ControlPoint &e2) {
  return e1.time < e2.time;
}

}

namespace noisicaa {

void CVRecipe::apply_mutation(pb::ProcessorMessage* msg) {
  if (msg->HasExtension(pb::cvgenerator_add_control_point)) {
    const pb::CVGeneratorAddControlPoint& m =
      msg->GetExtension(pb::cvgenerator_add_control_point);

    ControlPoint cp;
    cp.id = m.id();
    cp.time = m.time();
    cp.value = m.value();

    auto it = lower_bound(control_points.begin(), control_points.end(), cp, control_point_comp);
    control_points.insert(it, cp);
  } else if (msg->HasExtension(pb::cvgenerator_remove_control_point)) {
    const pb::CVGeneratorRemoveControlPoint& m =
      msg->GetExtension(pb::cvgenerator_remove_control_point);

    for (auto it = control_points.begin() ; it != control_points.end() ; ) {
      if (it->id == m.id()) {
        it = control_points.erase(it);
      } else {
        ++it;
      }
    }
  } else {
    assert(false);
  }

  // Invalidate recipe's cursor (so ProcessorCVGenerator::process_block() is forced to do a seek
  // first).
  offset = -1;
}

ProcessorCVGenerator::ProcessorCVGenerator(
    const string& realm_name, const string& node_id, HostSystem* host_system,
    const pb::NodeDescription& desc)
  : Processor(
      realm_name, node_id, "noisicaa.audioproc.engine.processor.cvgenerator", host_system, desc),
    _recipe_manager(_logger) {}

ProcessorCVGenerator::~ProcessorCVGenerator() {}

Status ProcessorCVGenerator::setup_internal() {
  return Processor::setup_internal();
}

void ProcessorCVGenerator::cleanup_internal() {
  Processor::cleanup_internal();
}

Status ProcessorCVGenerator::handle_message_internal(pb::ProcessorMessage* msg) {
  if (msg->HasExtension(pb::cvgenerator_add_control_point)
       || msg->HasExtension(pb::cvgenerator_remove_control_point)) {
    _recipe_manager.handle_mutation(msg);
    return Status::Ok();
  }

  return Processor::handle_message_internal(msg);
}

Status ProcessorCVGenerator::connect_port_internal(
    BlockContext* ctxt, uint32_t port_idx, BufferPtr buf) {
  assert(port_idx == 0);
  _out_buffer = buf;
  return Status::Ok();
}

Status ProcessorCVGenerator::process_block_internal(BlockContext* ctxt, TimeMapper* time_mapper) {
  PerfTracker tracker(ctxt->perf.get(), "cvgenerator");

  CVRecipe* recipe = _recipe_manager.get_current();

  assert(_out_buffer != nullptr);
  float* out_ptr = (float*)_out_buffer;

  SampleTime* stime = ctxt->time_map.get();
  for (uint32_t sample = 0 ; sample < _host_system->block_size() ; ++sample, ++stime) {
    if (stime->start_time.numerator() < 0) {
      // playback turned off
      recipe->offset = -1;
      *out_ptr++ = 0.0;
      continue;
    }

    float value;
    if (recipe->control_points.size() == 0) {
      value = 0.0;
    } else {
      if (recipe->offset < 0 || recipe->current_time != stime->start_time) {
        // Seek to new time.

        // TODO: We could to better than a sequential search.
        // - Do a binary search to find the new recipe->offset.

        recipe->offset = 0;
        while ((size_t)recipe->offset < recipe->control_points.size()) {
          const ControlPoint& cp = recipe->control_points[recipe->offset];

          if (cp.time >= stime->start_time) {
            break;
          }

          ++recipe->offset;
        }
      }

      if (recipe->offset == 0) {
        // Before first control point.
        const ControlPoint& cp = recipe->control_points[0];
        value = cp.value;
      } else if ((size_t)recipe->offset < recipe->control_points.size()) {
        // Between two control points.
        const ControlPoint& cp1 = recipe->control_points[recipe->offset - 1];
        const ControlPoint& cp2 = recipe->control_points[recipe->offset];
        value = cp1.value + (cp2.value - cp1.value) * (
            (stime->start_time - cp1.time) / (cp2.time - cp1.time)).to_float();
      } else {
        // After last control point.
        const ControlPoint& cp = recipe->control_points[recipe->control_points.size() - 1];
        value = cp.value;
      }

      // Advance to next control point, if needed. Might skip some control points, if
      // they are so close together that they all fall into the same sample.
      while ((size_t)recipe->offset < recipe->control_points.size()) {
        const ControlPoint& cp = recipe->control_points[recipe->offset];
        assert(cp.time >= stime->start_time);
        if (cp.time >= stime->end_time) {
          // no more events at this sample.
          break;
        }

        ++recipe->offset;
      }
    }

    *out_ptr++ = value;

    recipe->current_time = stime->end_time;
  }

  return Status::Ok();
}

}
