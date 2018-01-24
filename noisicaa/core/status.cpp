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

#include <stdarg.h>
#include <string.h>
#include "noisicaa/core/status.h"

namespace noisicaa {

Status Status::Error(const char* file, int line, const char* fmt, ...) {
  va_list args;
  va_start(args, fmt);

  char msg[10240];
  vsnprintf(msg, sizeof(msg), fmt, args);

  return Error(file, line, string(msg));
}

Status Status::OSError(const char* file, int line, const string& message) {
  char buf[1024];
  strncpy(buf, message.c_str(), sizeof(buf) - 1);
  buf[sizeof(buf) - 1] = '\0';

  strncat(buf, ": ", sizeof(buf) - strlen(buf) - 1);

  char ebuf[1024];
  strncat(buf, strerror_r(errno, ebuf, sizeof(ebuf)), sizeof(buf) - strlen(buf) - 1);

  return Status(Code::OS_ERROR, file, line, string(buf));
}

Status Status::OSError(const char* file, int line, const char* fmt, ...) {
  va_list args;
  va_start(args, fmt);

  char msg[10240];
  vsnprintf(msg, sizeof(msg), fmt, args);

  return OSError(file, line, string(msg));
}

}  // namespace noisicaa

