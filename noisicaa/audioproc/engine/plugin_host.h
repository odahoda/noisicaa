// -*- mode: c++ -*-

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

#ifndef _NOISICAA_AUDIOPROC_ENGINE_PLUGIN_HOST_H
#define _NOISICAA_AUDIOPROC_ENGINE_PLUGIN_HOST_H

#include <limits.h>
#include <pthread.h>
#include <sys/mman.h>
#include <atomic>
#include <string>
#include "noisicaa/core/status.h"
#include "noisicaa/audioproc/engine/buffers.h"
#include "noisicaa/audioproc/engine/plugin_host.pb.h"

namespace noisicaa {

using namespace std;

class Logger;
class HostSystem;
class PluginUIHost;
namespace pb {
class PluginState;
}

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
  const pb::NodeDescription& description() const { return _spec.node_description(); }

  virtual StatusOr<PluginUIHost*> create_ui(
      void* handle,
      void (*control_value_change_cb)(void*, uint32_t, float, uint32_t));

  virtual Status setup();
  virtual void cleanup();

  Status main_loop(int pipe_fd);
  void exit_loop();

  virtual Status connect_port(uint32_t port_idx, BufferPtr buf) = 0;
  virtual Status process_block(uint32_t block_size) = 0;

  virtual bool has_state() const;
  virtual StatusOr<string> get_state();
  Status set_state(const string& serialized_state);
  virtual Status set_state(const pb::PluginState& state);

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
