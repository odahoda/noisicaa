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

#ifndef _NOISICAA_AUDIOPROC_ENGINE_BLOCK_CONTEXT_H
#define _NOISICAA_AUDIOPROC_ENGINE_BLOCK_CONTEXT_H

#include <map>
#include <memory>
#include <string>
#include <vector>
#include <stdint.h>
#include "noisicaa/core/message.capnp.h"
#include "noisicaa/audioproc/public/musical_time.h"
#include "noisicaa/audioproc/engine/buffers.h"

namespace noisicaa {

class PerfStats;
class MessageQueue;
class BufferArena;

using namespace std;

struct SampleTime {
  MusicalTime start_time;
  MusicalTime end_time;
};

struct BlockContext {
  ~BlockContext();

  uint32_t sample_pos = 0;

  unique_ptr<PerfStats> perf;

  vector<SampleTime> time_map;

  BufferArena* buffer_arena;

  struct Buffer {
    size_t size;
    const BufferPtr data;
  };
  map<string, Buffer> buffers;

  // TODO: Use MessageQueue
  vector<string> in_messages;

  unique_ptr<MessageQueue> out_messages;
};

}  // namespace noisicaa

#endif
