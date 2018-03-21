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

#ifndef _NOISICAA_AUDIOPROC_ENGINE_BUFFER_ARENA_H
#define _NOISICAA_AUDIOPROC_ENGINE_BUFFER_ARENA_H

#include <string>
#include <stdint.h>
#include "noisicaa/core/status.h"
#include "noisicaa/audioproc/engine/buffers.h"

namespace noisicaa {

using namespace std;

class Logger;

class BufferArena {
public:
  BufferArena(size_t size, Logger* logger);
  ~BufferArena();

  Status setup();

  const string& name() const { return _name; }
  size_t size() const { return _size; }
  BufferPtr address() const { return _address; }

private:
  Logger* _logger;
  string _name;
  size_t _size;
  int _fd = -1;
  BufferPtr _address = nullptr;
};

}  // namespace noisicaa

#endif
