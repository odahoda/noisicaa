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

#ifndef _NOISICAA_AUDIOPROC_ENGINE_PROCESSOR_H
#define _NOISICAA_AUDIOPROC_ENGINE_PROCESSOR_H

#include <atomic>
#include <map>
#include <memory>
#include <string>
#include <stdint.h>
#include "noisicaa/core/logging.h"
#include "noisicaa/core/refcount.h"
#include "noisicaa/core/slots.h"
#include "noisicaa/core/status.h"
#include "noisicaa/node_db/node_description.pb.h"
#include "noisicaa/audioproc/public/musical_time.h"
#include "noisicaa/audioproc/public/node_parameters.pb.h"
#include "noisicaa/audioproc/engine/buffers.h"
#include "noisicaa/audioproc/engine/block_context.h"
#include "noisicaa/audioproc/engine/misc.h"

namespace noisicaa {

using namespace std;

class HostSystem;
class NotificationQueue;
class TimeMapper;
namespace pb {
class EngineNotification;
class ProcessorMessage;
}

// Keep this in sync with engine_notification.proto > NodeStateChange
enum ProcessorState {
  INACTIVE = 1,
  SETUP = 2,
  RUNNING = 3,
  BROKEN = 4,
  CLEANUP = 5,
};

class Processor : public RefCounted {
public:
  Processor(
      const string& realm_name, const string& node_id, const char* logger_name,
      HostSystem* host_system,
      const pb::NodeDescription& desc);
  virtual ~Processor();

  static StatusOr<Processor*> create(
      const string& realm_name, const string& node_id, HostSystem* host_system,
      const string& desc_serialized);

  uint64_t id() const { return _id; }
  const string& realm_name() const { return _realm_name; }
  const string& node_id() const { return _node_id; }
  ProcessorState state() const { return _state; }
  static const char* state_name(ProcessorState state);

  Status setup();
  virtual void cleanup();

  Status handle_message(const string& msg_serialized);
  Status set_parameters(const string& parameters_serialized);
  Status set_description(const string& description_serialized);

  void connect_port(BlockContext* ctxt, uint32_t port_idx, Buffer* buf);
  void process_block(BlockContext* ctxt, TimeMapper* time_mapper);

  Slot<pb::EngineNotification> notifications;

protected:
  void set_state(ProcessorState state);

  virtual Status setup_internal();
  virtual void cleanup_internal();

  virtual Status handle_message_internal(pb::ProcessorMessage* msg);
  virtual Status set_parameters_internal(const pb::NodeParameters& parameters);
  virtual Status set_description_internal(const pb::NodeDescription& description);
  virtual Status process_block_internal(BlockContext* ctxt, TimeMapper* time_mapper) = 0;
  virtual Status post_process_block_internal(BlockContext* ctxt, TimeMapper* time_mapper);

  void clear_all_outputs();

  Logger* _logger;
  HostSystem* _host_system;
  uint64_t _id;
  string _realm_name;
  string _node_id;
  pb::NodeDescription _desc;
  pb::NodeParameters _params;
  atomic<bool> _muted;
  vector<Buffer*> _buffers;
  bool _buffers_changed;

private:
  static uint64_t new_id();

  ProcessorState _state;
};

}  // namespace noisicaa

#endif
