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

#ifndef _NOISICAA_AUDIOPROC_ENGINE_PLUGIN_HOST_H
#define _NOISICAA_AUDIOPROC_ENGINE_PLUGIN_HOST_H

#include <limits.h>
#include <pthread.h>
#include <sys/mman.h>
#include <atomic>
#include "noisicaa/core/status.h"
#include "noisicaa/audioproc/engine/buffers.h"
#include "noisicaa/audioproc/engine/plugin_host.pb.h"

namespace noisicaa {

using namespace std;

class Logger;
class HostSystem;

struct PluginMemoryMapping {
  char shmem_path[PATH_MAX];
  size_t cond_offset;
  uint32_t block_size;
  uint32_t num_buffers;

  struct Buffer {
    uint32_t port_index;
    size_t offset;
  };
};

struct PluginCond {
  uint32_t magic;
  pthread_mutex_t mutex;
  pthread_cond_t cond;
  bool set;
};

class PluginHost {
public:
  virtual ~PluginHost();

  static StatusOr<PluginHost*> create(const string& spec_serialized, HostSystem* host_system);

  const string& node_id() const { return _spec.node_id(); }

  virtual Status setup();
  virtual void cleanup();

  Status main_loop(int pipe_fd);
  void exit_loop();

  virtual Status connect_port(uint32_t port_idx, BufferPtr buf) = 0;
  virtual Status process_block(uint32_t block_size) = 0;

protected:
  PluginHost(const pb::PluginInstanceSpec& spec, HostSystem* host_system, const char* logger_name);

  Logger* _logger;
  HostSystem* _host_system;
  pb::PluginInstanceSpec _spec;

private:
  Status handle_memory_map(PluginMemoryMapping* map, PluginMemoryMapping::Buffer* buffers);

  atomic<bool> _exit_loop;

  char _shmem_path[PATH_MAX] = "";
  int _shmem_fd = -1;
  void* _shmem_data = MAP_FAILED;
  size_t _shmem_size = 0;

  PluginCond* _cond = nullptr;
  uint32_t _block_size = 0;
};

}  // namespace noisicaa

#endif
