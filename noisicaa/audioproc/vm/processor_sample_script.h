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

#ifndef _NOISICAA_AUDIOPROC_VM_PROCESSOR_SAMPLE_SCRIPT_H
#define _NOISICAA_AUDIOPROC_VM_PROCESSOR_SAMPLE_SCRIPT_H

#include <stdint.h>
#include <atomic>
#include <memory>
#include <map>
#include <vector>
#include "noisicaa/core/status.h"
#include "noisicaa/audioproc/public/musical_time.h"
#include "noisicaa/audioproc/public/processor_message.pb.h"
#include "noisicaa/audioproc/vm/buffers.h"
#include "noisicaa/audioproc/vm/double_buffered_state_manager.h"
#include "noisicaa/audioproc/vm/processor.h"

namespace noisicaa {

class BlockContext;
class HostData;
class AudioFile;

class Sample {
public:
  uint64_t id;
  MusicalTime time;
  AudioFile* audio_file;
};

class SampleScript : public ManagedState<pb::ProcessorMessage> {
public:
  SampleScript(Logger* logger, HostData* host_data);
  ~SampleScript();

  vector<Sample> samples;

  int offset = -1;
  MusicalTime current_time = MusicalTime(0, 1);

  AudioFile* current_audio_file = nullptr;
  uint32_t file_offset;

  void apply_mutation(pb::ProcessorMessage* msg) override;

private:
  Logger* _logger;
  HostData* _host_data;
};

class ProcessorSampleScript : public Processor {
public:
  ProcessorSampleScript(const string& node_id, HostData* host_data);
  ~ProcessorSampleScript() override;

  Status setup(const ProcessorSpec* spec) override;
  void cleanup() override;

  Status connect_port(uint32_t port_idx, BufferPtr buf) override;
  Status run(BlockContext* ctxt, TimeMapper* time_mapper) override;

protected:
  Status handle_message_internal(pb::ProcessorMessage* msg) override;

private:
  BufferPtr _out_buffers[2];

  DoubleBufferedStateManager<SampleScript, pb::ProcessorMessage> _script_manager;
};

}  // namespace noisicaa

#endif
