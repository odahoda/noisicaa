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

#include "noisicaa/audioproc/engine/message_queue.h"
#include "noisicaa/audioproc/engine/rtcheck.h"

namespace noisicaa {

MessageQueue::MessageQueue()
  : _buf(new char[1 << 16]),
    _buf_size(1 << 16),
    _end(0) {}

MessageQueue::~MessageQueue() {}

Message* MessageQueue::allocate(size_t size) {
  size = 4 * ((size + 3) / 4);

  if (_end + size > _buf_size) {
    resize(max(2 * _buf_size, _end + size));
  }

  Message* msg = (Message*)(_buf.get() + _end);
  _end += size;
  return msg;
}

Status MessageQueue::push(const Message* msg) {
  Message* buf = allocate(msg->size);
  memmove(buf, msg, msg->size);
  return Status::Ok();
}

void MessageQueue::clear() {
  _end = 0;
}

void MessageQueue::resize(size_t size) {
  // TODO: make this more efficient (e.g. manage buffer in segments and just add segments without
  // moving existing data).
  RTUnsafe rtu;

  unique_ptr<char> buf(new char[size]);
  _buf_size = size;
  memmove(buf.get(), _buf.get(), _end);
  _buf.reset(buf.release());
}

}  // namespace noisicaa
