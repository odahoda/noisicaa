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
