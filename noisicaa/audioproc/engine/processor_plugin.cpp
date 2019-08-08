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

#include <assert.h>
#include <errno.h>
#include <poll.h>
#include <stdint.h>
#include <memory>
#include <string>
#include <chrono>
#include <pthread.h>
#include "noisicaa/core/perf_stats.h"
#include "noisicaa/host_system/host_system.h"
#include "noisicaa/audioproc/public/node_parameters.pb.h"
#include "noisicaa/audioproc/engine/plugin_host.h"
#include "noisicaa/audioproc/engine/buffer_arena.h"
#include "noisicaa/audioproc/engine/processor_plugin.pb.h"
#include "noisicaa/audioproc/engine/processor_plugin.h"
#include "noisicaa/audioproc/engine/rtcheck.h"

namespace noisicaa {

ProcessorPlugin::ProcessorPlugin(
    const string& realm_name, const string& node_id, HostSystem* host_system,
    const pb::NodeDescription& desc)
  : Processor(
      realm_name, node_id, "noisicaa.audioproc.engine.processor.plugin", host_system, desc) {
  auto* port = _desc.add_ports();
  port->set_direction(pb::PortDescription::INTERNAL_DIRECTION);
  port->add_types(pb::PortDescription::INTERNAL_TYPE);
  port->set_name("<internal cond>");
}

Status ProcessorPlugin::setup_internal() {
  _update_memmap = true;
  return Processor::setup_internal();
}

void ProcessorPlugin::cleanup_internal() {
  pipe_close();

  Processor::cleanup_internal();
}

Status ProcessorPlugin::set_parameters_internal(const pb::NodeParameters& parameters) {
  if (parameters.HasExtension(pb::processor_plugin_parameters)) {
    const auto& p = parameters.GetExtension(pb::processor_plugin_parameters);
    pipe_close();
    if (!p.plugin_pipe_path().empty()) {
      RETURN_IF_ERROR(pipe_open(p.plugin_pipe_path()));
    }
  }

  return Status::Ok();
}

Status ProcessorPlugin::process_block_internal(BlockContext* ctxt, TimeMapper* time_mapper) {
  PerfTracker tracker(ctxt->perf.get(), "plugin");

  if (_buffers_changed) {
    _update_memmap = true;
  }

  if (_pipe <= 0) {
    clear_all_outputs();
    return Status::Ok();
  }

  RTUnsafe rtu;  // We're doing IO in a (hopefully) RT safe way.

  auto timeout = chrono::seconds(2);
    //chrono::microseconds(1000000 * _host_system->block_size() / _host_system->sample_rate());

  deadline_t deadline = chrono::high_resolution_clock::now() + timeout;
  auto deadline_nsec = chrono::duration_cast<chrono::nanoseconds>(
      deadline.time_since_epoch()).count();
  timespec deadline_timespec;
  deadline_timespec.tv_sec = deadline_nsec / 1000000000;
  deadline_timespec.tv_nsec = deadline_nsec % 1000000000;

  uint32_t plugin_cond_idx = _desc.ports_size() - 1;
  PluginCond* plugin_cond = (PluginCond*)_buffers[plugin_cond_idx]->data();

  if (plugin_cond->magic != 0x34638a33) {
    return ERROR_STATUS("PluginCondBuffer not initialized.");
  }

  if (_update_memmap) {
    _logger->info("Sending PluginMemoryMapping...");

    char buf[64];
    snprintf(
        buf, sizeof(buf), "MEMORY_MAP\n%lu\n",
        sizeof(PluginMemoryMapping) + _desc.ports_size() * sizeof(PluginMemoryMapping::Buffer));
    RETURN_IF_ERROR(pipe_write(buf, strlen(buf), deadline));

    PluginMemoryMapping mapping;
    strncpy(mapping.shmem_path, ctxt->buffer_arena->name().c_str(), PATH_MAX);
    mapping.cond_offset = _buffers[plugin_cond_idx]->data() - ctxt->buffer_arena->address();
    mapping.block_size = _host_system->block_size();
    mapping.num_buffers = _desc.ports_size();

    RETURN_IF_ERROR(pipe_write((char*)&mapping, sizeof(mapping), deadline));

    for (int idx = 0 ; idx < _desc.ports_size() ; ++idx) {
      BufferPtr data = _buffers[idx]->data();
      assert(data >= ctxt->buffer_arena->address());
      assert(data < ctxt->buffer_arena->address() + ctxt->buffer_arena->size());

      PluginMemoryMapping::Buffer buf;
      buf.port_index = idx;
      buf.offset = data - ctxt->buffer_arena->address();
      RETURN_IF_ERROR(pipe_write((char*)&buf, sizeof(buf), deadline));
    }

    _update_memmap = false;
  }

  RETURN_IF_PTHREAD_ERROR(pthread_mutex_lock(&plugin_cond->mutex));
  plugin_cond->set = false;
  RETURN_IF_PTHREAD_ERROR(pthread_mutex_unlock(&plugin_cond->mutex));

  const char* cmd = "PROCESS_BLOCK\n";
  RETURN_IF_ERROR(pipe_write(cmd, strlen(cmd), deadline));

  RETURN_IF_PTHREAD_ERROR(pthread_mutex_lock(&plugin_cond->mutex));
  while (!plugin_cond->set) {
    if (chrono::high_resolution_clock::now() > deadline) {
      return TIMEOUT_STATUS();
    }

    RETURN_IF_PTHREAD_ERROR(pthread_cond_timedwait(
        &plugin_cond->cond, &plugin_cond->mutex, &deadline_timespec));
  }
  RETURN_IF_PTHREAD_ERROR(pthread_mutex_unlock(&plugin_cond->mutex));

  return Status::Ok();
}

Status ProcessorPlugin::pipe_open(const string& path) {
  assert(_pipe <= 0);

  _logger->info("Connecting to %s...", path.c_str());
  _pipe = open(path.c_str(), O_WRONLY | O_NONBLOCK);
  if (_pipe < 0) {
    return OSERROR_STATUS("Failed to open %s", path.c_str());
  }

  _update_memmap = true;

  return Status::Ok();
}

void ProcessorPlugin::pipe_close() {
  if (_pipe >= 0) {
    // uint32_t header[1] = { CLOSE };
    // Status status = pipe_write((const char*)header, sizeof(header));
    // if (status.is_error()) {
    //   _logger->error("Failed to write close message to pipe: %s", status.message());
    // }

    ::close(_pipe);
    _pipe = -1;
  }
}

Status ProcessorPlugin::pipe_write(const char* data, size_t size, deadline_t deadline) {
  while (size > 0) {
    auto time_remaining = deadline - chrono::high_resolution_clock::now();
    int msec_remaining = chrono::duration_cast<chrono::milliseconds>(time_remaining).count();
    if (msec_remaining <= 0) {
      return TIMEOUT_STATUS();
    }

    struct pollfd fds = {_pipe, POLLOUT, 0};
    int rc = poll(&fds, 1, min(500, msec_remaining));
    if (rc < 0) {
      return OSERROR_STATUS("Failed to poll out pipe");
    }

    if (fds.revents & POLLOUT) {
      ssize_t bytes_written = write(_pipe, data, size);
      if (bytes_written < 0) {
        if (errno == EPIPE) {
          return CONNECTION_CLOSED_STATUS();
        } else if (errno != 0) {
          return OSERROR_STATUS("Failed to write to pipe");
        }
      } else {
        data += bytes_written;
        size -= bytes_written;
      }
    } else if (fds.revents & POLLHUP) {
      return CONNECTION_CLOSED_STATUS();
    }
  }

  return Status::Ok();
}

}
