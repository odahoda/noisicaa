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

#ifndef _NOISICAA_BUILTIN_NODES_SAMPLE_TRACK_PROCESSOR_H
#define _NOISICAA_BUILTIN_NODES_SAMPLE_TRACK_PROCESSOR_H

#include <stdint.h>
#include <atomic>
#include <memory>
#include <map>
#include <vector>
#include "noisicaa/core/status.h"
#include "noisicaa/audioproc/public/musical_time.h"
#include "noisicaa/audioproc/public/processor_message.pb.h"
#include "noisicaa/audioproc/engine/buffers.h"
#include "noisicaa/audioproc/engine/double_buffered_state_manager.h"
#include "noisicaa/audioproc/engine/processor.h"

namespace noisicaa {

class BlockContext;
class HostSystem;
class AudioFile;

class Sample {
public:
  uint64_t id;
  MusicalTime time;
  AudioFile* audio_file;
};

class SampleScript : public ManagedState<pb::ProcessorMessage> {
public:
  SampleScript(Logger* logger, HostSystem* host_system);
  ~SampleScript();

  vector<Sample> samples;

  int offset = -1;
  MusicalTime current_time = MusicalTime(0, 1);

  AudioFile* current_audio_file = nullptr;
  uint32_t file_offset;

  void apply_mutation(Logger* logger, pb::ProcessorMessage* msg) override;

private:
  Logger* _logger;
  HostSystem* _host_system;
};

class ProcessorSampleScript : public Processor {
public:
  ProcessorSampleScript(
      const string& realm_name, const string& node_id, HostSystem* host_system,
      const pb::NodeDescription& desc);
  ~ProcessorSampleScript() override;

protected:
  Status setup_internal() override;
  void cleanup_internal() override;
  Status handle_message_internal(pb::ProcessorMessage* msg) override;
  Status process_block_internal(BlockContext* ctxt, TimeMapper* time_mapper) override;

private:
  DoubleBufferedStateManager<SampleScript, pb::ProcessorMessage> _script_manager;
};

}  // namespace noisicaa

#endif
