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

#include "noisicaa/core/logging.h"
#include "noisicaa/core/scope_guard.h"
#include "noisicaa/core/slots.inl.h"
#include "noisicaa/host_system/host_system.h"
#include "noisicaa/audioproc/public/devices.pb.h"
#include "noisicaa/audioproc/public/engine_notification.pb.h"
#include "noisicaa/audioproc/engine/misc.h"
#include "noisicaa/audioproc/engine/alsa_device_manager.h"

namespace noisicaa {

ALSADeviceManager::ALSADeviceManager(
    int client_id,
    Slot<pb::EngineNotification>& notifications)
  : _logger(LoggerRegistry::get_logger("noisicaa.audioproc.engine.backend.alsa_device_manager")),
    _client_id(client_id),
    _notifications(notifications) {}

ALSADeviceManager::~ALSADeviceManager() {
  for (const auto& it : _devices) {
    remove_device(it.second);
  }
  _devices.clear();

  if (_seq != nullptr) {
    snd_seq_close(_seq);
    _seq = nullptr;
  }
}

Status ALSADeviceManager::setup() {
  RETURN_IF_ALSA_ERROR(snd_seq_open(&_seq, "default", SND_SEQ_OPEN_DUPLEX, SND_SEQ_NONBLOCK));
  RETURN_IF_ALSA_ERROR(snd_seq_set_client_name(_seq, "noisicaa device monitor"));

  snd_seq_port_info_t *pinfo;
  snd_seq_port_info_alloca(&pinfo);

  snd_seq_port_info_set_capability(pinfo, SND_SEQ_PORT_CAP_WRITE | SND_SEQ_PORT_CAP_NO_EXPORT);
  snd_seq_port_info_set_type(pinfo, SND_SEQ_PORT_TYPE_APPLICATION);
  snd_seq_port_info_set_name(pinfo, "Input");
  RETURN_IF_ALSA_ERROR(snd_seq_create_port(_seq, pinfo));
  int input_port_id = snd_seq_port_info_get_port(pinfo);

  // Connect to System Announce port
  RETURN_IF_ALSA_ERROR(
      snd_seq_connect_from(
          _seq, input_port_id, SND_SEQ_CLIENT_SYSTEM, SND_SEQ_PORT_SYSTEM_ANNOUNCE));

  snd_seq_client_info_t *cinfo;
  snd_seq_client_info_alloca(&cinfo);
  snd_seq_client_info_set_client(cinfo, -1);
  while (snd_seq_query_next_client(_seq, cinfo) == 0) {
    int client_id = snd_seq_client_info_get_client(cinfo);
    if (client_id == snd_seq_client_id(_seq)
        || client_id == _client_id
        || client_id == SND_SEQ_CLIENT_SYSTEM) {
      continue;
    }

    StatusOr<pb::DeviceDescription> stor_device = get_device_description(client_id);
    RETURN_IF_ERROR(stor_device);
    pb::DeviceDescription device = stor_device.result();
    add_device(device);
    _devices[device.uri()] = device;
  }

  return Status::Ok();
}

StatusOr<pb::DeviceDescription> ALSADeviceManager::get_device_description(int client_id) {
  snd_seq_client_info_t *cinfo;
  snd_seq_client_info_alloca(&cinfo);

  snd_seq_port_info_t *pinfo;
  snd_seq_port_info_alloca(&pinfo);

  RETURN_IF_ALSA_ERROR(snd_seq_get_any_client_info(_seq, client_id, cinfo));

  pb::DeviceDescription device;
  device.set_uri(sprintf("alsa://%d", client_id));
  device.set_type(pb::DeviceDescription::MIDI_CONTROLLER);
  device.set_display_name(snd_seq_client_info_get_name(cinfo));

  snd_seq_port_info_set_client(pinfo, client_id);
  snd_seq_port_info_set_port(pinfo, -1);
  while (snd_seq_query_next_port(_seq, pinfo) == 0) {
    unsigned int cap = snd_seq_port_info_get_capability(pinfo);
    if (cap & SND_SEQ_PORT_CAP_NO_EXPORT) {
      continue;
    }

    pb::DevicePortDescription* port = device.add_ports();
    int port_id = snd_seq_port_info_get_port(pinfo);
    port->set_uri(sprintf("alsa://%d/%d", client_id, port_id));
    port->set_type(pb::DevicePortDescription::MIDI);
    port->set_display_name(snd_seq_port_info_get_name(pinfo));

    if (cap & (SND_SEQ_PORT_CAP_READ | SND_SEQ_PORT_CAP_DUPLEX)) {
      port->set_readable(true);
    }
    if (cap & (SND_SEQ_PORT_CAP_WRITE | SND_SEQ_PORT_CAP_DUPLEX)) {
      port->set_writable(true);
    }
  }

  return device;
}

void ALSADeviceManager::add_device(const pb::DeviceDescription& device) {
  _logger->info("Added device:\n%s", device.DebugString().c_str());

  pb::EngineNotification notification;
  pb::DeviceManagerMessage* m = notification.add_device_manager_messages();
  m->mutable_added()->CopyFrom(device);
  _notifications.emit(notification);
}

void ALSADeviceManager::update_device(const pb::DeviceDescription& device) {
  _logger->info("Updated device:\n%s", device.DebugString().c_str());

  pb::EngineNotification notification;
  pb::DeviceManagerMessage* m = notification.add_device_manager_messages();
  m->mutable_removed()->CopyFrom(device);
  m = notification.add_device_manager_messages();
  m->mutable_added()->CopyFrom(device);
  _notifications.emit(notification);
}

void ALSADeviceManager::remove_device(const pb::DeviceDescription& device) {
  _logger->info("Removed device:\n%s", device.DebugString().c_str());

  pb::EngineNotification notification;
  pb::DeviceManagerMessage* m = notification.add_device_manager_messages();
  m->mutable_removed()->CopyFrom(device);
  _notifications.emit(notification);
}

void ALSADeviceManager::process_events() {
  while (true) {
    snd_seq_event_t* event;
    int rc = snd_seq_event_input(_seq, &event);
    if (rc == -ENOSPC) {
      _logger->warning("ALSA midi queue overrun.");
      return;
    }
    if (rc == -EAGAIN) {
      return;
    }
    if (rc < 0) {
      _logger->error("ALSA error %d: %s", rc, snd_strerror(rc));
      return;
    }

    switch (event->type) {
    case SND_SEQ_EVENT_PORT_START:
    case SND_SEQ_EVENT_PORT_CHANGE:
    case SND_SEQ_EVENT_PORT_EXIT:
    case SND_SEQ_EVENT_CLIENT_START:
    case SND_SEQ_EVENT_CLIENT_CHANGE: {
      if (event->data.addr.client == snd_seq_client_id(_seq)
          || event->data.addr.client == _client_id
          || event->data.addr.client == SND_SEQ_CLIENT_SYSTEM) {
        break;
      }

      StatusOr<pb::DeviceDescription> stor_device = get_device_description(event->data.addr.client);
      if (stor_device.is_error()) {
        _logger->error(
            "Failed to get device description for ALSA sequencer client %d",
            event->data.addr.client);
      } else {
        pb::DeviceDescription device = stor_device.result();

        auto it = _devices.find(device.uri());
        if (it == _devices.end()) {
          add_device(device);
          _devices[device.uri()] = device;
        } else if (!google::protobuf::util::MessageDifferencer::Equals(device, it->second)) {
          update_device(device);
          _devices[device.uri()] = device;
        }
      }
      break;
    }

    case SND_SEQ_EVENT_CLIENT_EXIT: {
      if (event->data.addr.client == snd_seq_client_id(_seq)
          || event->data.addr.client == _client_id
          || event->data.addr.client == SND_SEQ_CLIENT_SYSTEM) {
        break;
      }

      string uri = sprintf("alsa://%d", event->data.addr.client);
      auto it = _devices.find(uri);
      if (it == _devices.end()) {
        _logger->warning("Got CLIENT_EXIT event for unknown client.");
      } else {
        remove_device(it->second);
        _devices.erase(it);
      }
      break;
    }

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
      break;
    }
  }
}

}  // namespace noisicaa
