#include "noisicaa/audioproc/vm/message_queue.h"

namespace noisicaa {

MessageQueue::MessageQueue()
  : _buf(new char[1 << 16]),
    _buf_size(1 << 16),
    _end(0) {}

MessageQueue::~MessageQueue() {}

Status MessageQueue::push(const Message* msg) {
  if (_end + msg->size > _buf_size) {
    resize(max(2 * _buf_size, _end + msg->size));
  }

  memmove(_buf.get() + _end, msg, msg->size);
  _end += 4 * ((msg->size + 3) / 4);

  return Status::Ok();
}

void MessageQueue::clear() {
  _end = 0;
}

void MessageQueue::resize(size_t size) {
  unique_ptr<char> buf(new char[size]);
  memmove(buf.get(), _buf.get(), _end);
  _buf.reset(buf.release());
}

}  // namespace noisicaa
