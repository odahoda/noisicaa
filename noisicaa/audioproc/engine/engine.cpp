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
    _out_messages_pump(nullptr),
    _next_out_messages(new MessageQueue()),
    _current_out_messages(nullptr),
    _old_out_messages(new MessageQueue()) {}

Engine::~Engine() {}

Status Engine::setup() {
  _stop = false;
  _out_messages_pump.reset(new thread(&Engine::out_messages_pump_main, this));

  return Status::Ok();
}

void Engine::cleanup() {
  if (_out_messages_pump.get() != nullptr) {
    _logger->info("Stopping out_messages pump...");
    {
      lock_guard<mutex> lock(_cond_mutex);
      _stop = true;
      _cond.notify_all();
    }

    _out_messages_pump->join();
    _out_messages_pump.reset();
    _logger->info("out_messages pump stopped.");
  }

  MessageQueue* out_messages = _next_out_messages.exchange(nullptr);
  if (out_messages != nullptr) {
    delete out_messages;
  }
  out_messages = _current_out_messages.exchange(nullptr);
  if (out_messages != nullptr) {
    delete out_messages;
  }
  out_messages = _old_out_messages.exchange(nullptr);
  if (out_messages != nullptr) {
    delete out_messages;
  }
}

void Engine::out_messages_pump_main() {
  unique_lock<mutex> lock(_cond_mutex);
  while (true) {
    _cond.wait_for(lock, chrono::milliseconds(500));

    MessageQueue* out_messages = _old_out_messages.exchange(nullptr);
    if (out_messages != nullptr) {
      if (!out_messages->empty()) {
        pb::EngineNotification notification;

        Message* msg = out_messages->first();
        while (!out_messages->is_end(msg)) {
          switch (msg->type) {

          case MessageType::ENGINE_LOAD: {
            EngineLoadMessage* tmsg = (EngineLoadMessage*)msg;
            auto n = notification.add_engine_load();
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

          msg = out_messages->next(msg);
        }
        out_messages->clear();

        string notification_serialized;
        assert(notification.SerializeToString(&notification_serialized));
        _callback(_userdata, notification_serialized);
      }

      out_messages = _next_out_messages.exchange(out_messages);
      if (out_messages != nullptr) {
        assert(_old_out_messages.exchange(out_messages) == nullptr);
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

    MessageQueue* out_messages = _next_out_messages.exchange(nullptr);
    if (out_messages != nullptr) {
      assert(out_messages->empty());
      MessageQueue* old = _current_out_messages.exchange(nullptr);
      if (old != nullptr) {
        assert(_old_out_messages.exchange(old) == nullptr);
        _cond.notify_all();
      }
    } else {
      out_messages = _current_out_messages.exchange(nullptr);
      assert(out_messages != nullptr);
    }
    ctxt->out_messages = out_messages;

    if (ctxt->perf->num_spans() > 0) {
      PerfStatsMessage::push(ctxt->out_messages, *ctxt->perf);
    }
    ctxt->perf->reset();

    ctxt->input_events = nullptr;

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
      RETURN_IF_ERROR(backend->output(ctxt, Backend::Channel::AUDIO_LEFT, buf->data()));
    }

    buf = realm->get_buffer("sink:in:right");
    if(buf != nullptr) {
      RETURN_IF_ERROR(backend->output(ctxt, Backend::Channel::AUDIO_RIGHT, buf->data()));
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
    assert(_current_out_messages.exchange(out_messages) == nullptr);
  }

  return Status::Ok();
}

}  // namespace noisicaa
