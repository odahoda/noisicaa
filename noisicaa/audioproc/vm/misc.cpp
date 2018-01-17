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

#include <memory>
#include <stdio.h>
#include <stdarg.h>
#include "noisicaa/audioproc/vm/misc.h"

namespace noisicaa {

string sprintf(const string &fmt, ...) {
  va_list args;
  va_start(args, fmt);

  int size = std::vsnprintf(nullptr, 0, fmt.c_str(), args) + 1;
  unique_ptr<char> buf(new char[size]);

  va_start(args, fmt);
  std::vsnprintf(buf.get(), size, fmt.c_str(), args);
  return string(buf.get());
}

}
