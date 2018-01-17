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

#include <algorithm>

#include "noisicaa/core/perf_stats.h"
#include "noisicaa/audioproc/vm/misc.h"
#include "noisicaa/audioproc/vm/host_data.h"
#include "noisicaa/audioproc/vm/double_buffered_state_manager.inl.h"
#include "noisicaa/audioproc/vm/processor_message.pb.h"
#include "noisicaa/audioproc/vm/processor_cvgenerator.h"

namespace {

using namespace std;
using namespace noisicaa;

bool control_point_comp(const ControlPoint &e1, const ControlPoint &e2) {
  return e1.time < e2.time;
}

}

namespace noisicaa {

void CVRecipe::apply_mutation(pb::ProcessorMessage* msg) {
  switch (msg->msg_case()) {
  case pb::ProcessorMessage::kCvgeneratorAddControlPoint: {
    const pb::ProcessorMessage::CVGeneratorAddControlPoint& m = msg->cvgenerator_add_control_point();

    ControlPoint cp;
    cp.id = m.id();
    cp.time = m.time();
    cp.value = m.value();

    auto it = lower_bound(control_points.begin(), control_points.end(), cp, control_point_comp);
    control_points.insert(it, cp);
    break;
  }

  case pb::ProcessorMessage::kCvgeneratorRemoveControlPoint: {
    const pb::ProcessorMessage::CVGeneratorRemoveControlPoint& m =
      msg->cvgenerator_remove_control_point();

    for (auto it = control_points.begin() ; it != control_points.end() ; ) {
      if (it->id == m.id()) {
        it = control_points.erase(it);
      } else {
        ++it;
      }
    }
    break;
  }

  default:
    assert(false);
  }

  // Invalidate recipe's cursor (so ProcessorCVGenerator::run() is forced to do a seek first).
  offset = -1;
}

ProcessorCVGenerator::ProcessorCVGenerator(const string& node_id, HostData* host_data)
  : Processor(node_id, "noisicaa.audioproc.vm.processor.cvgenerator", host_data),
    _recipe_manager(_logger) {}

ProcessorCVGenerator::~ProcessorCVGenerator() {}

Status ProcessorCVGenerator::setup(const ProcessorSpec* spec) {
  return Processor::setup(spec);
}

void ProcessorCVGenerator::cleanup() {
  Processor::cleanup();
}

Status ProcessorCVGenerator::handle_message_internal(pb::ProcessorMessage* msg) {
  switch (msg->msg_case()) {
  case pb::ProcessorMessage::kCvgeneratorAddControlPoint:
  case pb::ProcessorMessage::kCvgeneratorRemoveControlPoint:
    _recipe_manager.handle_mutation(msg);
    return Status::Ok();

  default:
    return Processor::handle_message_internal(msg);
  }
}

Status ProcessorCVGenerator::connect_port(uint32_t port_idx, BufferPtr buf) {
  assert(port_idx == 0);
  _out_buffer = buf;
  return Status::Ok();
}

Status ProcessorCVGenerator::run(BlockContext* ctxt, TimeMapper* time_mapper) {
  PerfTracker tracker(ctxt->perf.get(), "cvgenerator");

  CVRecipe* recipe = _recipe_manager.get_current();

  assert(_out_buffer != nullptr);
  float* out_ptr = (float*)_out_buffer;

  for (uint32_t sample = 0 ; sample < ctxt->block_size ; ++sample) {
    const SampleTime& stime = ctxt->time_map[sample];

    if (stime.start_time.numerator() < 0) {
      // playback turned off
      recipe->offset = -1;
      *out_ptr++ = 0.0;
      continue;
    }

    float value;
    if (recipe->control_points.size() == 0) {
      value = 0.0;
    } else {
      if (recipe->offset < 0 || recipe->current_time != stime.start_time) {
        // Seek to new time.

        // TODO: We could to better than a sequential search.
        // - Do a binary search to find the new recipe->offset.

        recipe->offset = 0;
        while ((size_t)recipe->offset < recipe->control_points.size()) {
          const ControlPoint& cp = recipe->control_points[recipe->offset];

          if (cp.time >= stime.start_time) {
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
            (stime.start_time - cp1.time) / (cp2.time - cp1.time)).to_float();
      } else {
        // After last control point.
        const ControlPoint& cp = recipe->control_points[recipe->control_points.size() - 1];
        value = cp.value;
      }

      // Advance to next control point, if needed. Might skip some control points, if
      // they are so close together that they all fall into the same sample.
      while ((size_t)recipe->offset < recipe->control_points.size()) {
        const ControlPoint& cp = recipe->control_points[recipe->offset];
        assert(cp.time >= stime.start_time);
        if (cp.time >= stime.end_time) {
          // no more events at this sample.
          break;
        }

        ++recipe->offset;
      }
    }

    *out_ptr++ = value;

    recipe->current_time = stime.end_time;
  }

  return Status::Ok();
}

}
