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

#include <string>
#include <ctype.h>
#include <stdint.h>
#include "noisicaa/core/status.h"
#include "noisicaa/core/slots.inl.h"
#include "noisicaa/host_system/host_system.h"
#include "noisicaa/audioproc/public/engine_notification.pb.h"
#include "noisicaa/audioproc/engine/message_queue.h"
#include "noisicaa/audioproc/engine/misc.h"
#include "noisicaa/builtin_nodes/processor_message_registry.pb.h"
#include "noisicaa/builtin_nodes/custom_csound/processor_messages.pb.h"
#include "noisicaa/builtin_nodes/custom_csound/processor.h"

namespace {

using namespace std;

string port_name_to_csound_label(const string &port_name) {
  string result;
  bool was_alpha = false;
  for (const auto& c : port_name) {
    bool is_alpha = isalpha(c);
    if (is_alpha && !was_alpha) {
      result += toupper(c);
    } else if (is_alpha) {
      result += c;
    }
    was_alpha = is_alpha;
  }

  return result;
}

}  // namespace

namespace noisicaa {

ProcessorCustomCSound::ProcessorCustomCSound(
    const string& realm_name, const string& node_id, HostSystem *host_system,
    const pb::NodeDescription& desc)
  : ProcessorCSoundBase(
      realm_name, node_id, "noisicaa.audioproc.engine.processor.custom_csound", host_system, desc) {
  _csound_log_urid = _host_system->lv2->map(
      "http://noisicaa.odahoda.de/lv2/processor_custom_csound#csound-log");
}

Status ProcessorCustomCSound::setup_internal() {
  RETURN_IF_ERROR(ProcessorCSoundBase::setup_internal());

  return Status::Ok();
}

void ProcessorCustomCSound::cleanup_internal() {
  ProcessorCSoundBase::cleanup_internal();
}

Status ProcessorCustomCSound::handle_message_internal(pb::ProcessorMessage* msg) {
  if (msg->HasExtension(pb::custom_csound_set_script)) {
    unique_ptr<pb::ProcessorMessage> msg_ptr(msg);

    const auto& m = msg->GetExtension(pb::custom_csound_set_script);

    string orchestra_preamble = "0dbfs = 1.0\nksmps = 32\nnchnls = 2\n";

    for (int i = 0 ; i < _desc.ports_size() ; ++i) {
      const auto& port = _desc.ports(i);

      if (port.type() == pb::PortDescription::AUDIO
          && port.direction() == pb::PortDescription::INPUT) {
        orchestra_preamble += sprintf(
            "ga%s chnexport \"%s\", 1\n",
            port_name_to_csound_label(port.name()).c_str(),
            port.name().c_str());
      } else if (port.type() == pb::PortDescription::AUDIO
                 && port.direction() == pb::PortDescription::OUTPUT) {
        orchestra_preamble += sprintf(
            "ga%s chnexport \"%s\", 2\n",
            port_name_to_csound_label(port.name()).c_str(),
            port.name().c_str());
      } else if (port.type() == pb::PortDescription::ARATE_CONTROL
                 && port.direction() == pb::PortDescription::INPUT) {
        orchestra_preamble += sprintf(
            "ga%s chnexport \"%s\", 1\n",
            port_name_to_csound_label(port.name()).c_str(),
            port.name().c_str());
      } else if (port.type() == pb::PortDescription::ARATE_CONTROL
                 && port.direction() == pb::PortDescription::OUTPUT) {
        orchestra_preamble += sprintf(
            "ga%s chnexport \"%s\", 2\n",
            port_name_to_csound_label(port.name()).c_str(),
            port.name().c_str());
      } else if (port.type() == pb::PortDescription::KRATE_CONTROL
                 && port.direction() == pb::PortDescription::INPUT) {
        orchestra_preamble += sprintf(
            "gk%s chnexport \"%s\", 1\n",
            port_name_to_csound_label(port.name()).c_str(),
            port.name().c_str());
      } else if (port.type() == pb::PortDescription::KRATE_CONTROL
                 && port.direction() == pb::PortDescription::OUTPUT) {
        orchestra_preamble += sprintf(
            "gk%s chnexport \"%s\", 2\n",
            port_name_to_csound_label(port.name()).c_str(),
            port.name().c_str());
      } else if (port.type() == pb::PortDescription::EVENTS
                 && port.direction() == pb::PortDescription::INPUT) {
      } else {
        return ERROR_STATUS("Port %s not supported", port.name().c_str());
      }
    }

    string orchestra = orchestra_preamble + m.orchestra();
    _logger->info("Orchestra:\n%s", orchestra.c_str());
    _logger->info("Score:\n%s", m.score().c_str());
    Status status = set_code(orchestra, m.score());
    if (status.is_error()) {
      _logger->warning("Failed to update script: %s", status.message());
    }

    return Status::Ok();
  }

  return Processor::handle_message_internal(msg);
}

Status ProcessorCustomCSound::process_block_internal(BlockContext* ctxt, TimeMapper* time_mapper) {
  _ctxt = ctxt;
  Status status = ProcessorCSoundBase::process_block_internal(ctxt, time_mapper);
  _ctxt = nullptr;

  return status;
}

void ProcessorCustomCSound::handle_csound_log(LogLevel level, const char* msg) {
  ProcessorCSoundBase::handle_csound_log(level, msg);

  uint8_t atom[10000];
  LV2_Atom_Forge forge;
  lv2_atom_forge_init(&forge, &_host_system->lv2->urid_map);
  lv2_atom_forge_set_buffer(&forge, atom, sizeof(atom));

  LV2_Atom_Forge_Frame frame;
  lv2_atom_forge_object(&forge, &frame, _host_system->lv2->urid.core_nodemsg, 0);
  lv2_atom_forge_key(&forge, _csound_log_urid);
  lv2_atom_forge_string(&forge, msg, strlen(msg));
  lv2_atom_forge_pop(&forge, &frame);

  if (_ctxt != nullptr) {
    // In the audio thread. Publish node message via the message queue.
    NodeMessage::push(_ctxt->out_messages, _node_id, (LV2_Atom*)atom);
  } else {
    // Not in the audio thread. Publish node message directly as a proto message.

    pb::EngineNotification notification;
    auto m = notification.add_node_messages();
    m->set_node_id(_node_id);
    m->set_atom(atom, ((LV2_Atom*)atom)->size + sizeof(LV2_Atom));
    notifications.emit(notification);
  }
}

}
