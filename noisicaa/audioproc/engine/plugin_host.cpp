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
#include <fcntl.h>
#include <poll.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include "noisicaa/core/logging.h"
#include "noisicaa/node_db/node_description.pb.h"
#include "noisicaa/host_system/host_system.h"
#include "noisicaa/audioproc/public/plugin_state.pb.h"
#include "noisicaa/audioproc/engine/plugin_host.h"
#include "noisicaa/audioproc/engine/plugin_host_lv2.h"
#include "noisicaa/audioproc/engine/plugin_host_ladspa.h"
#include "noisicaa/audioproc/engine/realtime.h"

namespace noisicaa {

PluginHost::PluginHost(
    const pb::PluginInstanceSpec& spec, HostSystem* host_system, const char* logger_name)
  : _logger(LoggerRegistry::get_logger(logger_name)),
    _host_system(host_system),
    _spec(spec) {}

PluginHost::~PluginHost() {}

StatusOr<PluginHost*> PluginHost::create(const string& spec_serialized, HostSystem* host_system) {
  pb::PluginInstanceSpec spec;
  assert(spec.ParseFromString(spec_serialized));

  const pb::NodeDescription& desc = spec.node_description();
  assert(desc.has_plugin());

  switch (desc.plugin().type()) {
  case pb::PluginDescription::LV2:
    return new PluginHostLV2(spec, host_system);

  case pb::PluginDescription::LADSPA:
    return new PluginHostLadspa(spec, host_system);

  default:
    return ERROR_STATUS(
        "Invalid node type '%s'",
        pb::PluginDescription::Type_Name(desc.plugin().type()).c_str());
  }

}

StatusOr<PluginUIHost*> PluginHost::create_ui(
    void* handle, void (*control_value_change_cb)(void*, uint32_t, float, uint32_t)) {
  return ERROR_STATUS("Plugin does not support UIs.");
}

Status PluginHost::setup() {
  _logger->info("Setting up plugin host %s...", _spec.node_id().c_str());

  _exit_loop.store(false);

  return Status::Ok();
}

void PluginHost::cleanup() {
  if (_shmem_data != MAP_FAILED) {
    munmap(_shmem_data, _shmem_size);
    _shmem_data = nullptr;
    _shmem_size = 0;
  }

  if (_shmem_fd >= 0) {
    close(_shmem_fd);
    _shmem_fd = -1;
  }

  _logger->info("Plugin host %s cleaned up.", _spec.node_id().c_str());
}


bool PluginHost::has_state() const {
  return false;
}

StatusOr<string> PluginHost::get_state() {
  return ERROR_STATUS("Not supported by this plugin.");
}

Status PluginHost::set_state(const string& serialized_string) {
  pb::PluginState state;
  assert(state.ParseFromString(serialized_string));
  return set_state(state);
}

Status PluginHost::set_state(const pb::PluginState& state) {
  return ERROR_STATUS("Not supported by this plugin.");
}

Status PluginHost::main_loop(int pipe_fd) {
  _logger->info("Entering main loop...");

  RETURN_IF_ERROR(set_thread_to_rt_priority(_logger));

  enum State { READ_COMMAND, READ_MEMMAP_SIZE, READ_MEMMAP };
  State state = READ_COMMAND;

  char buf[20480];
  size_t buf_size = 0;
  size_t memmap_size = 0;
  while (!_exit_loop.load()) {
    struct pollfd fds[] = {
      {pipe_fd, POLLIN, 0},
    };
    int rc = poll(fds, 1, 1000);
    if (rc < 0) {
      return OSERROR_STATUS("Failed to poll in pipe");
    }

    if (fds[0].revents & POLLIN) {
      ssize_t bytes_read = read(pipe_fd, buf + buf_size, sizeof(buf) - buf_size);
      if (bytes_read < 0) {
        return OSERROR_STATUS("Failed to read from pipe");
      }
      buf_size += bytes_read;
    } else if (fds[0].revents & POLLHUP) {
      return CONNECTION_CLOSED_STATUS();
    }

    bool more;
    do {
      more = false;
      switch (state) {
      case READ_COMMAND: {
        char* lf = (char*)memchr(buf, '\n', buf_size);
        if (lf == nullptr) {
          break;
        }

        *lf = 0;
        if (strcmp(buf, "PROCESS_BLOCK") == 0) {
          if (_shmem_data == MAP_FAILED) {
            return ERROR_STATUS("PROCESS_MAP before memory mapping was set.");
          }

          RETURN_IF_ERROR(process_block(_block_size));

          RETURN_IF_PTHREAD_ERROR(pthread_mutex_lock(&_cond->mutex));
          _cond->set = true;
          RETURN_IF_PTHREAD_ERROR(pthread_mutex_unlock(&_cond->mutex));
          RETURN_IF_PTHREAD_ERROR(pthread_cond_signal(&_cond->cond));
        } else if (strcmp(buf, "MEMORY_MAP") == 0) {
          state = READ_MEMMAP_SIZE;
        } else {
          return ERROR_STATUS("Unknown command '%s' received.", buf);
        }

        buf_size -= lf + 1 - buf;
        memmove(buf, lf + 1, buf_size);
        if (buf_size > 0) {
          more = true;
        }
        break;
      }
      case READ_MEMMAP_SIZE: {
        char* lf = (char*)memchr(buf, '\n', buf_size);
        if (lf == nullptr) {
          break;
        }

        *lf = 0;
        memmap_size = strtol(buf, nullptr, 10);
        if (memmap_size > sizeof(buf)) {
          return ERROR_STATUS("Invalid memory map size %lu", memmap_size);
        }
        state = READ_MEMMAP;

        buf_size -= lf + 1 - buf;
        memmove(buf, lf + 1, buf_size);
        if (buf_size > 0) {
          more = true;
        }
        break;
      }
      case READ_MEMMAP: {
        if (buf_size < memmap_size) {
          break;
        }

        RETURN_IF_ERROR(handle_memory_map(
            (PluginMemoryMapping*)buf,
            (PluginMemoryMapping::Buffer*)(buf + sizeof(PluginMemoryMapping))));

        state = READ_COMMAND;

        buf_size -= memmap_size;
        memmove(buf, buf + memmap_size, buf_size);
        if (buf_size > 0) {
          more = true;
        }
        break;
      }
      }
    } while (more);
  }
  _logger->info("Main loop finished.");

  return Status::Ok();
}

void PluginHost::exit_loop() {
  _exit_loop.store(true);
}

Status PluginHost::handle_memory_map(PluginMemoryMapping* map, PluginMemoryMapping::Buffer* buffers) {
  if (strcmp(map->shmem_path, _shmem_path) != 0) {
    _logger->info("Using new shared memory location %s...", map->shmem_path);

    if (_shmem_data != MAP_FAILED) {
      munmap(_shmem_data, _shmem_size);
      _shmem_data = nullptr;
      _shmem_size = 0;
    }

    if (_shmem_fd >= 0) {
      close(_shmem_fd);
      _shmem_fd = -1;
    }

    _shmem_fd = shm_open(map->shmem_path, O_RDWR, 0);
    if (_shmem_fd < 0) {
      return OSERROR_STATUS("Failed to open shmem %s", map->shmem_path);
    }

    strcpy(_shmem_path, map->shmem_path);

    struct stat s;
    if (fstat(_shmem_fd, &s) < 0) {
      return OSERROR_STATUS("Failed to stat shmem %s", map->shmem_path);
    }
    _shmem_size = s.st_size;

    _shmem_data = mmap(nullptr, _shmem_size, PROT_READ | PROT_WRITE, MAP_SHARED, _shmem_fd, 0);
    if (_shmem_data == MAP_FAILED) {
      return OSERROR_STATUS("Failed to mmap shmem %s", map->shmem_path);
    }
  }

  _logger->info("cond_offset=%u", map->cond_offset);
  _cond = (PluginCond*)((char*)_shmem_data + map->cond_offset);
  if (_cond->magic != 0x34638a33) {
    return ERROR_STATUS("PluginCondBuffer not initialized.");
  }

  _logger->info("block_size=%u", map->block_size);
  _block_size = map->block_size;

  _logger->info("num_buffers=%u", map->num_buffers);
  for (size_t i = 0 ; i < map->num_buffers ; ++i) {
    _logger->info("port %u offset=%u", buffers[i].port_index, buffers[i].offset);
    BufferPtr buf = (BufferPtr)((char*)_shmem_data + buffers[i].offset);
    RETURN_IF_ERROR(connect_port(buffers[i].port_index, buf));
  }

  return Status::Ok();
}

}  // namespace noisicaa
