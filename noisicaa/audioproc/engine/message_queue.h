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

#ifndef _NOISICAA_AUDIOPROC_ENGINE_MESSAGE_QUEUE_H
#define _NOISICAA_AUDIOPROC_ENGINE_MESSAGE_QUEUE_H

#include <memory>
#include <string.h>

#include "lv2/lv2plug.in/ns/ext/atom/atom.h"

#include "noisicaa/core/perf_stats.h"
#include "noisicaa/core/status.h"
#include "noisicaa/audioproc/public/musical_time.h"

namespace noisicaa {

using namespace std;

class MessageQueue;

enum MessageType {
  ENGINE_LOAD = 1,
  PERF_STATS = 2,
  PLAYER_STATE = 3,
  NODE_MESSAGE = 4,
};

struct Message {
  MessageType type;
  size_t size;

private:
  Message() = delete;
};

class MessageQueue {
public:
  MessageQueue();
  ~MessageQueue();

  Message* allocate(size_t size);
  Status push(const Message* msg);
  void clear();

  Message* first() const {
    return (Message*)_buf.get();
  }

  Message* next(Message* it) const {
    return (Message*)((char*)it + it->size);
  }

  bool is_end(Message* it) const {
    return (char*)it >= _buf.get() + _end;
  }

  bool empty() const {
    return _end == 0;
  }

private:
  void resize(size_t size);

  unique_ptr<char> _buf;
  size_t _buf_size;
  size_t _end;
};

struct EngineLoadMessage : Message {
  static EngineLoadMessage* push(
      MessageQueue* queue,
      double load) {
    EngineLoadMessage* msg = (EngineLoadMessage*)queue->allocate(sizeof(EngineLoadMessage));
    msg->type = ENGINE_LOAD;
    msg->size = sizeof(EngineLoadMessage);
    msg->load = load;

    return msg;
  }

  double load;

private:
  EngineLoadMessage() = delete;
};

struct PerfStatsMessage : Message {
  static PerfStatsMessage* push(
      MessageQueue* queue,
      const PerfStats& perf_stats) {
    size_t length = perf_stats.serialized_size();

    PerfStatsMessage* msg = (PerfStatsMessage*)queue->allocate(sizeof(PerfStatsMessage) + length);
    msg->type = PERF_STATS;
    msg->size = sizeof(PerfStatsMessage) + length;
    msg->length = length;
    perf_stats.serialize_to(msg->perf_stats());

    return msg;
  }

  size_t length;
  char *perf_stats(void) { return ((char*)this) + sizeof(PerfStatsMessage); }

private:
  PerfStatsMessage() = delete;
};

struct PlayerStateMessage : Message {
  static PlayerStateMessage* push(
      MessageQueue* queue,
      const string& realm,
      bool playing,
      const MusicalTime& current_time,
      bool loop_enabled,
      const MusicalTime& loop_start_time,
      const MusicalTime& loop_end_time) {
    assert(realm.size() + 1 < 256);

    PlayerStateMessage* msg = (PlayerStateMessage*)queue->allocate(sizeof(PlayerStateMessage));
    msg->type = PLAYER_STATE;
    msg->size = sizeof(PlayerStateMessage);
    strcpy(msg->realm, realm.c_str());
    msg->playing = playing;
    msg->current_time = current_time;
    msg->loop_enabled = loop_enabled;
    msg->loop_start_time = loop_start_time;
    msg->loop_end_time = loop_end_time;

    return msg;
  }

  char realm[256];
  bool playing;
  MusicalTime current_time;
  bool loop_enabled;
  MusicalTime loop_start_time;
  MusicalTime loop_end_time;

private:
  PlayerStateMessage() = delete;
};

struct NodeMessage : Message {
  static NodeMessage* push(
      MessageQueue* queue,
      const string& node_id,
      const LV2_Atom* atom) {
    NodeMessage* msg = (NodeMessage*)queue->allocate(
        sizeof(NodeMessage) + sizeof(LV2_Atom) + atom->size);
    msg->type = MessageType::NODE_MESSAGE;
    msg->size = sizeof(NodeMessage) + sizeof(LV2_Atom) + atom->size;

    strncpy(msg->node_id, node_id.c_str(), sizeof(msg->node_id));
    memmove(msg->atom(), atom, sizeof(LV2_Atom) + atom->size);

    return msg;
  }

  char node_id[256];
  LV2_Atom* atom() { return (LV2_Atom*)(this + 1); }
  const LV2_Atom* atom() const { return (LV2_Atom*)(this + 1); }
  size_t atom_size() const { return sizeof(LV2_Atom) + atom()->size; }

private:
  NodeMessage() = delete;
};

}  // namespace noisicaa

#endif
