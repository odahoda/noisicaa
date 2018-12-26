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

#include <assert.h>
#include <errno.h>
#include <stdarg.h>
#include <string.h>
#include <stdlib.h>
#include <stdio.h>
#include "noisicaa/core/status.h"

namespace noisicaa {

thread_local char Status::_messages[Status::NumMessageSlots][Status::MaxMessageLength] = {
  "", "", "", "", "", "", "", "", "", ""
};

int Status::allocate_message(const char* msg) {
  if (*msg == 0) {
    return -1;
  }

  if (strcmp(msg, "Uninitialized status") == 0) {
    return -2;
  }

  assert(strlen(msg) + 1 < MaxMessageLength);
  for (int i = 0 ; i < NumMessageSlots ; ++i) {
    if (_messages[i][0] == 0) {
      strcpy(_messages[i], msg);
      return i;
    }
  }
  for (int i = 0 ; i < NumMessageSlots ; ++i) {
    fprintf(stderr, "% 2d: %s\n", i, _messages[i]);
  }
  abort();
}

const char* Status::message() const {
  switch (_message) {
  case -2: return "Uninitialized status";
  case -1: return "";
  default:
    assert(_message >= 0 && _message < NumMessageSlots);
    return _messages[_message];
  }
}

Status Status::Error(const char* file, int line, const char* fmt, ...) {
  va_list args;
  va_start(args, fmt);

  char msg[MaxMessageLength];
  vsnprintf(msg, sizeof(msg), fmt, args);

  return Status(Code::ERROR, file, line, msg);
}

Status Status::OSError(const char* file, int line, const char* fmt, ...) {
  va_list args;
  va_start(args, fmt);

  char msg[MaxMessageLength];
  vsnprintf(msg, sizeof(msg), fmt, args);

  strncat(msg, ": ", sizeof(msg) - strlen(msg) - 1);

  char ebuf[MaxMessageLength];
  strncat(msg, strerror_r(errno, ebuf, sizeof(ebuf)), sizeof(msg) - strlen(msg) - 1);

  return Status(Code::OS_ERROR, file, line, msg);
}

}  // namespace noisicaa

