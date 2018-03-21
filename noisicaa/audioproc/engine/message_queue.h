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
#include "noisicaa/core/status.h"

namespace noisicaa {

using namespace std;

enum MessageType {
  SOUND_FILE_COMPLETE = 1,
  PORT_RMS = 2,
};

struct Message {
  Message(MessageType t, size_t s) : type(t), size(s) {}

  MessageType type;
  size_t size;
};

struct NodeMessage : Message {
  NodeMessage(const string& n, MessageType t, size_t s)
    : Message(t, s) {
    strncpy(node_id, n.c_str(), sizeof(node_id));
  }

  char node_id[256];
};

struct SoundFileCompleteMessage : NodeMessage {
  SoundFileCompleteMessage(const string& node_id)
    : NodeMessage(node_id, SOUND_FILE_COMPLETE, sizeof(SoundFileCompleteMessage)) {}
};

struct PortRMSMessage : NodeMessage {
  PortRMSMessage(const string& node_id, uint32_t port_index, float rms)
    : NodeMessage(node_id, PORT_RMS, sizeof(PortRMSMessage)),
      port_index(port_index),
      rms(rms) {}

  uint32_t port_index;
  float rms;
};

class MessageQueue {
public:
  MessageQueue();
  ~MessageQueue();

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

private:
  void resize(size_t size);

  unique_ptr<char> _buf;
  size_t _buf_size;
  size_t _end;
};

}  // namespace noisicaa

#endif
