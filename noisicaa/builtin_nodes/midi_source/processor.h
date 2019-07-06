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

#ifndef _NOISICAA_BUILTIN_NODES_MIDI_SOURCE_PROCESSOR_H
#define _NOISICAA_BUILTIN_NODES_MIDI_SOURCE_PROCESSOR_H

#include <atomic>
#include <memory>
#include <vector>
#include "noisicaa/core/fifo_queue.h"
#include "noisicaa/core/status.h"
#include "noisicaa/audioproc/engine/processor.h"

namespace noisicaa {

using namespace std;

class HostSystem;

class ProcessorMidiSource : public Processor {
public:
  ProcessorMidiSource(
      const string& realm_name, const string& node_id, HostSystem* host_system,
      const pb::NodeDescription& desc);

protected:
  Status setup_internal() override;
  void cleanup_internal() override;
  Status handle_message_internal(pb::ProcessorMessage* msg) override;
  Status process_block_internal(BlockContext* ctxt, TimeMapper* time_mapper) override;

private:
  struct Config {
    string device_uri;
    int32_t channel_filter;
  };
  atomic<Config*> _next_config;
  atomic<Config*> _current_config;
  atomic<Config*> _old_config;

  struct ClientMessage {
    uint8_t midi[3];
  };
  FifoQueue<ClientMessage, 20> _client_messages;

  Config _config;
  Status update_config();
};

}  // namespace noisicaa

#endif
