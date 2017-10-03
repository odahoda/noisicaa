// -*- mode: c++ -*-

#ifndef _NOISICAA_AUDIOPROC_VM_MESSAGE_QUEUE_H
#define _NOISICAA_AUDIOPROC_VM_MESSAGE_QUEUE_H

#include <memory>
#include <string.h>
#include "noisicaa/core/status.h"

namespace noisicaa {

using namespace std;

enum MessageType {
  SOUND_FILE_COMPLETE = 1,
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
