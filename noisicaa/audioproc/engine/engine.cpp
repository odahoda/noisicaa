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
#include <sys/types.h>
#include <sys/syscall.h>
#include <chrono>
#include <thread>

#include "noisicaa/core/scope_guard.h"
#include "noisicaa/core/perf_stats.h"
#include "noisicaa/audioproc/public/engine_notification.pb.h"
#include "noisicaa/audioproc/engine/block_context.h"
#include "noisicaa/audioproc/engine/engine.h"
#include "noisicaa/audioproc/engine/message_queue.h"
#include "noisicaa/audioproc/engine/profile.h"
#include "noisicaa/audioproc/engine/realtime.h"
#include "noisicaa/audioproc/engine/rtcheck.h"

namespace noisicaa {

Engine::Engine(HostSystem* host_system, void (*callback)(void*, const string&), void *userdata)
  : _host_system(host_system),
    _logger(LoggerRegistry::get_logger("noisicaa.audioproc.engine.engine")),
    _callback(callback),
    _userdata(userdata),
    _queue_pump(nullptr),
    _next_message_queue(new MessageQueue()),
    _current_message_queue(nullptr),
    _old_message_queue(new MessageQueue()) {}

Engine::~Engine() {}

Status Engine::setup() {
  _stop = false;
  _queue_pump.reset(new thread(&Engine::queue_pump_main, this));

  return Status::Ok();
}

void Engine::cleanup() {
  if (_queue_pump.get() != nullptr) {
    _logger->info("Stopping queue pump...");
    {
      lock_guard<mutex> lock(_cond_mutex);
      _stop = true;
      _cond.notify_all();
    }

    _queue_pump->join();
    _queue_pump.reset();
    _logger->info("Queue pump stopped.");
  }

  MessageQueue* message_queue = _next_message_queue.exchange(nullptr);
  if (message_queue != nullptr) {
    delete message_queue;
  }
  message_queue = _current_message_queue.exchange(nullptr);
  if (message_queue != nullptr) {
    delete message_queue;
  }
  message_queue = _old_message_queue.exchange(nullptr);
  if (message_queue != nullptr) {
    delete message_queue;
  }
}

void Engine::queue_pump_main() {
  unique_lock<mutex> lock(_cond_mutex);
  while (true) {
    _cond.wait_for(lock, chrono::milliseconds(500));

    MessageQueue* queue = _old_message_queue.exchange(nullptr);
    if (queue != nullptr) {
      if (!queue->empty()) {
        pb::EngineNotification notification;

        Message* msg = queue->first();
        while (!queue->is_end(msg)) {
          switch (msg->type) {

          case MessageType::ENGINE_LOAD: {
            EngineLoadMessage* tmsg = (EngineLoadMessage*)msg;
            auto n = notification.add_engine_state_changes();
            n->set_state(pb::EngineStateChange::RUNNING);
            n->set_load(tmsg->load);
            break;
          }

          case MessageType::PERF_STATS: {
            PerfStatsMessage* tmsg = (PerfStatsMessage*)msg;
            notification.set_perf_stats(tmsg->perf_stats(), tmsg->length);
            break;
          }

          case MessageType::PLAYER_STATE: {
            PlayerStateMessage* tmsg = (PlayerStateMessage*)msg;
            auto n = notification.mutable_player_state();
            n->set_realm(tmsg->realm);
            n->set_playing(tmsg->playing);
            tmsg->current_time.set_proto(n->mutable_current_time());
            n->set_loop_enabled(tmsg->loop_enabled);
            tmsg->loop_start_time.set_proto(n->mutable_loop_start_time());
            tmsg->loop_end_time.set_proto(n->mutable_loop_end_time());
            break;
          }

          case MessageType::NODE_MESSAGE: {
            NodeMessage* tmsg = (NodeMessage*)msg;
            auto n = notification.add_node_messages();
            n->set_node_id(tmsg->node_id);
            n->set_atom(tmsg->atom(), tmsg->atom_size());
            break;
          }

          default: {
            _logger->error("Unexpected message type %d", msg->type);
            break;
          }
          }

          msg = queue->next(msg);
        }
        queue->clear();

        string notification_serialized;
        assert(notification.SerializeToString(&notification_serialized));
        _callback(_userdata, notification_serialized);
      }

      queue = _next_message_queue.exchange(queue);
      if (queue != nullptr) {
        assert(_old_message_queue.exchange(queue) == nullptr);
      }
    }

    if (_stop) {
      break;
    }
  }
}

Status Engine::setup_thread() {
  _exit_loop = false;

  RETURN_IF_ERROR(set_thread_to_rt_priority(_logger));

  return Status::Ok();
}

void Engine::exit_loop() {
  _exit_loop = true;
}

Status Engine::loop(Realm* realm, Backend* backend) {
  assert(realm != nullptr);
  assert(backend != nullptr);

  enable_profiling_in_thread();

  _logger->info("Audio thread: PID=%d TID=%ld", getpid(), syscall(__NR_gettid));
  RTSafe rts;  // Enable rtchecker in audio thread.

  chrono::high_resolution_clock::time_point last_loop_time =
    chrono::high_resolution_clock::time_point::min();

  while (!_exit_loop) {
    BlockContext* ctxt = realm->block_context();

    StatusOr<Program*> stor_program = realm->get_active_program();
    RETURN_IF_ERROR(stor_program);
    Program* program = stor_program.result();
    if (program == nullptr) {
      this_thread::sleep_for(chrono::milliseconds(100));
      continue;
    }

    MessageQueue* current_queue = _next_message_queue.exchange(nullptr);
    if (current_queue != nullptr) {
      assert(current_queue->empty());
      MessageQueue* old = _current_message_queue.exchange(nullptr);
      if (old != nullptr) {
        assert(_old_message_queue.exchange(old) == nullptr);
        _cond.notify_all();
      }
    } else {
      current_queue = _current_message_queue.exchange(nullptr);
      assert(current_queue != nullptr);
    }
    ctxt->out_messages = current_queue;

    if (ctxt->perf->num_spans() > 0) {
      PerfStatsMessage::push(ctxt->out_messages, *ctxt->perf);
    }
    ctxt->perf->reset();

    RETURN_IF_ERROR(backend->begin_block(ctxt));
    auto auto_end_block = scopeGuard([this, backend, ctxt]() {
        Status status = backend->end_block(ctxt);
        if (status.is_error()) {
          _logger->error(
              "Backend::end_block() failed: %s:%d %s",
              status.file(), status.line(), status.message());
        }
      });

    RETURN_IF_ERROR(realm->process_block(program));

    Buffer* buf = realm->get_buffer("sink:in:left");
    if(buf != nullptr) {
      RETURN_IF_ERROR(backend->output(ctxt, "left", buf->data()));
    }

    buf = realm->get_buffer("sink:in:right");
    if(buf != nullptr) {
      RETURN_IF_ERROR(backend->output(ctxt, "right", buf->data()));
    }

    if (last_loop_time > chrono::high_resolution_clock::time_point::min()) {
      auto loop_duration = chrono::high_resolution_clock::now() - last_loop_time;
      double loop_usec = std::chrono::duration_cast<std::chrono::microseconds>(loop_duration).count();
      double block_usec = 1e6 * _host_system->block_size() / _host_system->sample_rate();
      double load = loop_usec / block_usec;
      EngineLoadMessage::push(ctxt->out_messages, load);
    }

    auto_end_block.dismiss();
    RETURN_IF_ERROR(backend->end_block(ctxt));

    last_loop_time = chrono::high_resolution_clock::now();

    ctxt->out_messages = nullptr;
    assert(_current_message_queue.exchange(current_queue) == nullptr);
  }

  return Status::Ok();
}

}  // namespace noisicaa
