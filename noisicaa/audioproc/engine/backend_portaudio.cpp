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

#include <google/protobuf/util/message_differencer.h>

#include "noisicaa/core/perf_stats.h"
#include "noisicaa/core/scope_guard.h"
#include "noisicaa/host_system/host_system.h"
#include "noisicaa/audioproc/public/devices.pb.h"
#include "noisicaa/audioproc/public/engine_notification.pb.h"
#include "noisicaa/audioproc/engine/backend_portaudio.h"
#include "noisicaa/audioproc/engine/realm.h"
#include "noisicaa/audioproc/engine/rtcheck.h"
#include "noisicaa/audioproc/engine/alsa_device_manager.h"

namespace noisicaa {

PortAudioBackend::PortAudioBackend(
    HostSystem* host_system, const pb::BackendSettings& settings,
    void (*callback)(void*, const string&), void *userdata)
  : Backend(host_system, "noisicaa.audioproc.engine.backend.portaudio", settings, callback, userdata),
    _initialized(false),
    _stream(nullptr),
    _samples{nullptr, nullptr},
    _seq(nullptr),
    _events(nullptr) {
}

PortAudioBackend::~PortAudioBackend() {}

Status PortAudioBackend::setup(Realm* realm) {
  RETURN_IF_ERROR(Backend::setup(realm));

  PaError err = Pa_Initialize();
  if (err != paNoError) {
    return ERROR_STATUS("Failed to initialize portaudio: %s", Pa_GetErrorText(err));
  }
  _initialized = true;

  RETURN_IF_ERROR(setup_stream());

  _device_thread_stop.exchange(false);
  StatusSignal status;
  _device_thread.reset(new thread(&PortAudioBackend::device_thread_main, this, &status));
  RETURN_IF_ERROR(status.wait());

  RETURN_IF_ALSA_ERROR(snd_seq_open(&_seq, "default", SND_SEQ_OPEN_DUPLEX, SND_SEQ_NONBLOCK));
  RETURN_IF_ALSA_ERROR(snd_seq_set_client_name(_seq, "noisicaa"));
  _client_id = snd_seq_client_id(_seq);

  snd_seq_port_info_t *pinfo;
  snd_seq_port_info_alloca(&pinfo);
  snd_seq_port_info_set_capability(pinfo, SND_SEQ_PORT_CAP_WRITE);
  snd_seq_port_info_set_type(
      pinfo, SND_SEQ_PORT_TYPE_MIDI_GENERIC | SND_SEQ_PORT_TYPE_APPLICATION);
  snd_seq_port_info_set_name(pinfo, "Input");
  RETURN_IF_ALSA_ERROR(snd_seq_create_port(_seq, pinfo));
  _input_port_id = snd_seq_port_info_get_port(pinfo);

  // Connect to System Announce port
  RETURN_IF_ALSA_ERROR(
      snd_seq_connect_from(
          _seq, _input_port_id, SND_SEQ_CLIENT_SYSTEM, SND_SEQ_PORT_SYSTEM_ANNOUNCE));

  snd_seq_client_info_t *cinfo;
  snd_seq_client_info_alloca(&cinfo);
  snd_seq_client_info_set_client(cinfo, -1);
  while (snd_seq_query_next_client(_seq, cinfo) == 0) {
    int client_id = snd_seq_client_info_get_client(cinfo);
    if (client_id == snd_seq_client_id(_seq) || client_id == SND_SEQ_CLIENT_SYSTEM) {
      continue;
    }

    snd_seq_port_info_t *pinfo;
    snd_seq_port_info_alloca(&pinfo);
    snd_seq_port_info_set_client(pinfo, client_id);
    snd_seq_port_info_set_port(pinfo, -1);
    while (snd_seq_query_next_port(_seq, pinfo) == 0) {
      int port_id = snd_seq_port_info_get_port(pinfo);
      unsigned int cap = snd_seq_port_info_get_capability(pinfo);
      if (cap & SND_SEQ_PORT_CAP_READ && !(cap & SND_SEQ_PORT_CAP_NO_EXPORT)) {
        RETURN_IF_ALSA_ERROR(
            snd_seq_connect_from(_seq, _input_port_id, client_id, port_id));
        _logger->info(
            "Listening to MIDI sequencer port %d.%d",
            client_id, port_id);
      }
    }
  }

  _events = new uint8_t[10240];

  return Status::Ok();
}

void PortAudioBackend::cleanup() {
  if (_events != nullptr) {
    delete _events;
    _events = nullptr;
  }

  if (_seq != nullptr) {
    snd_seq_close(_seq);
    _seq = nullptr;
  }

  if (_device_thread.get() != nullptr) {
    _device_thread_stop = true;
    _device_thread->join();
    _device_thread.reset();
  }

  cleanup_stream();

  if (_initialized) {
    PaError err = Pa_Terminate();
    if (err != paNoError) {
      _logger->error("Failed to terminate portaudio: %s", Pa_GetErrorText(err));
    }
    _initialized = false;
  }

  Backend::cleanup();
}

Status PortAudioBackend::setup_stream() {
  assert(_stream == nullptr);

  PaDeviceIndex device_index = Pa_GetDefaultOutputDevice();
  const PaDeviceInfo* device_info = Pa_GetDeviceInfo(device_index);
  _logger->info("PortAudio device: %s", device_info->name);

  PaStreamParameters output_params;
  output_params.device = device_index;
  output_params.channelCount = 2;
  output_params.sampleFormat = paFloat32 | paNonInterleaved;
  output_params.suggestedLatency = device_info->defaultLowOutputLatency;
  output_params.hostApiSpecificStreamInfo = nullptr;

  PaError err;

  err = Pa_OpenStream(
      /* stream */            &_stream,
      /* inputParameters */   NULL,
      /* outputParameters */  &output_params,
      /* sampleRate */        _host_system->sample_rate(),
      /* framesPerBuffer */   _host_system->block_size(),
      /* streamFlags */       paNoFlag,
      /* streamCallback */    nullptr,
      /* userdata */          nullptr);
  if (err != paNoError) {
    return ERROR_STATUS("Failed to open portaudio stream: %s", Pa_GetErrorText(err));
  }

  err = Pa_StartStream(_stream);
  if (err != paNoError) {
    return ERROR_STATUS("Failed to start portaudio stream: %s", Pa_GetErrorText(err));
  }

  for (int c = 0 ; c < 2 ; ++c) {
    assert(_samples[c] == nullptr);
    _samples[c] = new uint8_t[_host_system->block_size() * sizeof(float)];
  }

  return Status::Ok();
}

void PortAudioBackend::cleanup_stream() {
  for (int c = 0 ; c < 2 ; ++c) {
    if (_samples[c] != nullptr) {
      delete _samples[c];
      _samples[c] = nullptr;
    }
  }

  if (_stream != nullptr) {
    PaError err = Pa_CloseStream(_stream);
    if (err != paNoError) {
      _logger->error("Failed to close portaudio stream: %s", Pa_GetErrorText(err));
    }
    _stream = nullptr;
  }
}

void PortAudioBackend::device_thread_main(StatusSignal* status) {
  _logger->info("Starting ALSA device listener thread...");
  auto goodbye = scopeGuard([this]() {
      _logger->info("ALSA device listener thread stopped");
    });

  ALSADeviceManager mgr(_client_id, notifications);
  Status mgr_status = mgr.setup();
  if (mgr_status.is_error()) {
    status->set(mgr_status);
    return;
  }

  status->set(Status::Ok());

  while (!_device_thread_stop.load()) {
    std::this_thread::sleep_for(std::chrono::milliseconds(10));

    mgr.process_events();
  }
}

Status PortAudioBackend::begin_block(BlockContext* ctxt) {
  assert(ctxt->perf->current_span_id() == 0);
  ctxt->perf->start_span("frame");

  for (int c = 0 ; c < 2 ; ++c) {
    memset(_samples[c], 0, _host_system->block_size() * sizeof(float));
  }

  LV2_Atom_Forge forge;
  lv2_atom_forge_init(&forge, &_host_system->lv2->urid_map);

  LV2_Atom_Forge_Frame frame;
  lv2_atom_forge_set_buffer(&forge, _events, 10240);
  lv2_atom_forge_sequence_head(&forge, &frame, _host_system->lv2->urid.atom_frame_time);

  while (true) {
    snd_seq_event_t* event;
    int rc = snd_seq_event_input(_seq, &event);
    if (rc == -ENOSPC) {
      _logger->warning("ALSA midi queue overrun.");
      break;
    }
    if (rc == -EAGAIN) {
      break;
    }
    RETURN_IF_ALSA_ERROR(rc);

    if ((event->flags & SND_SEQ_TIME_STAMP_MASK) != SND_SEQ_TIME_STAMP_TICK) {
      _logger->error("Event without tick");
      continue;
    }

    switch (event->type) {
    case SND_SEQ_EVENT_NOTEON: {
      _logger->debug(
          "Note on: time=%d source=%d.%d channel=%d note=%d velocity=%d",
          event->time.tick,
          event->source.client, event->source.port,
          event->data.note.channel,
          event->data.note.note,
          event->data.note.velocity);

      char uri[128];
      snprintf(uri, sizeof(uri), "alsa://%d/%d", event->source.client, event->source.port);

      uint8_t msg[3];
      msg[0] = 0x90 | event->data.note.channel;
      msg[1] = event->data.note.note;
      msg[2] = event->data.note.velocity;

      lv2_atom_forge_frame_time(&forge, 0);
      LV2_Atom_Forge_Frame tframe;
      lv2_atom_forge_tuple(&forge, &tframe);
      lv2_atom_forge_string(&forge, uri, strlen(uri));
      lv2_atom_forge_atom(&forge, 3, _host_system->lv2->urid.midi_event);
      lv2_atom_forge_write(&forge, msg, 3);
      lv2_atom_forge_pop(&forge, &tframe);
      break;
    }

    case SND_SEQ_EVENT_NOTEOFF: {
      _logger->debug(
          "Note off: time=%d source=%d.%d channel=%d note=%d velocity=%d",
          event->time.tick,
          event->source.client, event->source.port,
          event->data.note.channel,
          event->data.note.note,
          event->data.note.velocity);

      char uri[128];
      snprintf(uri, sizeof(uri), "alsa://%d/%d", event->source.client, event->source.port);

      uint8_t msg[3];
      msg[0] = 0x80 | event->data.note.channel;
      msg[1] = event->data.note.note;
      msg[2] = event->data.note.velocity;

      lv2_atom_forge_frame_time(&forge, 0);
      LV2_Atom_Forge_Frame tframe;
      lv2_atom_forge_tuple(&forge, &tframe);
      lv2_atom_forge_string(&forge, uri, strlen(uri));
      lv2_atom_forge_atom(&forge, 3, _host_system->lv2->urid.midi_event);
      lv2_atom_forge_write(&forge, msg, 3);
      lv2_atom_forge_pop(&forge, &tframe);
      break;
    }

    case SND_SEQ_EVENT_CONTROLLER:
      _logger->debug(
          "CC: time=%d source=%d.%d channel=%d, param=%d value=%d",
          event->time.tick,
          event->source.client, event->source.port,
          event->data.control.channel,
          event->data.control.param,
          event->data.control.value);
      char uri[128];
      snprintf(uri, sizeof(uri), "alsa://%d/%d", event->source.client, event->source.port);

      uint8_t msg[3];
      msg[0] = 0xb0 | event->data.control.channel;
      msg[1] = event->data.control.param;
      msg[2] = event->data.control.value;

      lv2_atom_forge_frame_time(&forge, 0);
      LV2_Atom_Forge_Frame tframe;
      lv2_atom_forge_tuple(&forge, &tframe);
      lv2_atom_forge_string(&forge, uri, strlen(uri));
      lv2_atom_forge_atom(&forge, 3, _host_system->lv2->urid.midi_event);
      lv2_atom_forge_write(&forge, msg, 3);
      lv2_atom_forge_pop(&forge, &tframe);
      break;

    case SND_SEQ_EVENT_PORT_START: {
      snd_seq_port_info_t *pinfo;
      snd_seq_port_info_alloca(&pinfo);
      int rc = snd_seq_get_any_port_info(
          _seq, event->data.addr.client, event->data.addr.port, pinfo);
      if (rc < 0) {
        _logger->error("ALSA error %d: %s", rc, snd_strerror(rc));
      } else {
        unsigned int cap = snd_seq_port_info_get_capability(pinfo);
        if (cap & SND_SEQ_PORT_CAP_READ && !(cap & SND_SEQ_PORT_CAP_NO_EXPORT)) {
          rc = snd_seq_connect_from(
              _seq, _input_port_id, event->data.addr.client, event->data.addr.port);
          if (rc < 0) {
            _logger->error("ALSA error %d: %s", rc, snd_strerror(rc));
          } else {
            _logger->info(
                "Listening to MIDI sequencer port %d.%d",
                event->data.addr.client, event->data.addr.port);
          }
        }
      }
      break;
    }

    case SND_SEQ_EVENT_PORT_CHANGE:
    case SND_SEQ_EVENT_PORT_EXIT:
    case SND_SEQ_EVENT_CLIENT_START:
    case SND_SEQ_EVENT_CLIENT_CHANGE:
    case SND_SEQ_EVENT_CLIENT_EXIT:
    case SND_SEQ_EVENT_PORT_SUBSCRIBED:
    case SND_SEQ_EVENT_PORT_UNSUBSCRIBED:
      // Ignore these events.
      break;

    default:
      _logger->error(
          "Unknown MIDI event: type=%d flags=%x tag=%x queue=%x time=%d source=%d.%d dest=%d.%d",
          event->type,
          event->flags,
          event->tag,
          event->queue,
          event->time.tick,
          event->source.client,
          event->source.port,
          event->dest.client,
          event->dest.port);
    }
  }

  lv2_atom_forge_pop(&forge, &frame);

  ctxt->input_events = (LV2_Atom_Sequence*)_events;

  return Status::Ok();
}

Status PortAudioBackend::end_block(BlockContext* ctxt) {
  ctxt->perf->end_span();
  assert(ctxt->perf->current_span_id() == 0);

  RTUnsafe rtu;  // portaudio does malloc in Pa_WriteStream.

  PaError err = Pa_WriteStream(_stream, _samples, _host_system->block_size());
  if (err == paOutputUnderflowed) {
    _logger->warning("Buffer underrun.");
  } else if (err != paNoError) {
    return ERROR_STATUS("Failed to write to portaudio stream: %s", Pa_GetErrorText(err));
  }
  return Status::Ok();
}

Status PortAudioBackend::output(BlockContext* ctxt, Channel channel, BufferPtr samples) {
  switch (channel) {
  case AUDIO_LEFT:
    memmove(_samples[0], samples, _host_system->block_size() * sizeof(float));
    return Status::Ok();
  case AUDIO_RIGHT:
    memmove(_samples[1], samples, _host_system->block_size() * sizeof(float));
    return Status::Ok();
  default:
    return ERROR_STATUS("Invalid channel %d", channel);
  }
}

}  // namespace noisicaa
