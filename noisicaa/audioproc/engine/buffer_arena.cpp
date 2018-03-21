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

#include <fcntl.h>
#include <unistd.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <random>

#include "noisicaa/core/logging.h"
#include "noisicaa/audioproc/engine/misc.h"
#include "noisicaa/audioproc/engine/buffer_arena.h"

namespace noisicaa {

BufferArena::BufferArena(size_t size, Logger* logger)
  : _logger(logger),
    _size(size) {}

BufferArena::~BufferArena() {
  if (_address != nullptr) {
    _logger->info("Deleting buffer arena %s.", _name.c_str());
    munmap(_address, _size);
  }

  if (_fd >= 0) {
    close(_fd);
    _fd = -1;

    if (shm_unlink(_name.c_str())) {
      _logger->warning("Failed to unlink shmem %s", _name.c_str());
    }
  }
}

Status BufferArena::setup() {
  random_device rand;
  _name = sprintf("/noisicaa-bufferarena-%08x-%08x", time(0), rand());

  _logger->info("Creating buffer arena %s with %lu bytes...", _name.c_str(), _size);

  _fd = shm_open(_name.c_str(), O_CREAT | O_EXCL | O_RDWR, S_IRUSR | S_IWUSR);
  if (_fd < 0) {
    return OSERROR_STATUS("Failed to open shmem %s", _name.c_str());
  }

  if (ftruncate(_fd, _size) < 0) {
    return OSERROR_STATUS("Failed to resize shmem %s", _name.c_str());
  }

  void* address = mmap(nullptr, _size, PROT_READ | PROT_WRITE, MAP_SHARED, _fd, 0);
  if (address == MAP_FAILED) {
    return OSERROR_STATUS("Failed to mmap shmem %s", _name.c_str());
  }
  _address = (BufferPtr)address;

  return Status::Ok();
}

}  // namespace noisicaa
