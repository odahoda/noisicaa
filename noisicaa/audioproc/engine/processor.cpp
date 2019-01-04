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

#include <random>
#include <time.h>
#include "lv2/lv2plug.in/ns/ext/atom/forge.h"
#include "lv2/lv2plug.in/ns/ext/urid/urid.h"

#include "noisicaa/core/slots.inl.h"
#include "noisicaa/host_system/host_system.h"
#include "noisicaa/audioproc/public/processor_message.pb.h"
#include "noisicaa/audioproc/engine/processor.pb.h"
#include "noisicaa/audioproc/engine/processor.h"
#include "noisicaa/audioproc/engine/processor_null.h"
#include "noisicaa/audioproc/engine/processor_csound.h"
#include "noisicaa/audioproc/engine/processor_custom_csound.h"
#include "noisicaa/audioproc/engine/processor_instrument.h"
#include "noisicaa/audioproc/engine/processor_plugin.h"
#include "noisicaa/audioproc/engine/processor_sound_file.h"
#include "noisicaa/audioproc/engine/processor_mixer.h"
#include "noisicaa/audioproc/engine/processor_pianoroll.h"
#include "noisicaa/audioproc/engine/processor_cvgenerator.h"
#include "noisicaa/audioproc/engine/processor_sample_script.h"

namespace noisicaa {

Processor::Processor(
    const string& node_id, const char* logger_name, HostSystem* host_system,
    const pb::NodeDescription& desc)
  : _logger(LoggerRegistry::get_logger(logger_name)),
    _host_system(host_system),
    _id(Processor::new_id()),
    _node_id(node_id),
    _desc(desc),
    _state(ProcessorState::INACTIVE) {}

Processor::~Processor() {}

StatusOr<Processor*> Processor::create(
    const string& node_id, HostSystem* host_system, const string& desc_serialized) {
  pb::NodeDescription desc;
  if (!desc.ParseFromString(desc_serialized)) {
    return ERROR_STATUS("Failed to parse NodeDescription proto.");
  }

  assert(desc.has_processor());

  switch (desc.processor().type()) {
  case pb::ProcessorDescription::NULLPROC:
    assert(desc.type() == pb::NodeDescription::PROCESSOR);
    return new ProcessorNull(node_id, host_system, desc);
  case pb::ProcessorDescription::CSOUND:
    assert(desc.type() == pb::NodeDescription::PROCESSOR);
    return new ProcessorCSound(node_id, host_system, desc);
  case pb::ProcessorDescription::CUSTOM_CSOUND:
    assert(desc.type() == pb::NodeDescription::PROCESSOR);
    return new ProcessorCustomCSound(node_id, host_system, desc);
  case pb::ProcessorDescription::PLUGIN:
    assert(desc.type() == pb::NodeDescription::PLUGIN);
    return new ProcessorPlugin(node_id, host_system, desc);
  case pb::ProcessorDescription::INSTRUMENT:
    assert(desc.type() == pb::NodeDescription::PROCESSOR);
    return new ProcessorInstrument(node_id, host_system, desc);
  case pb::ProcessorDescription::SOUND_FILE:
    assert(desc.type() == pb::NodeDescription::PROCESSOR);
    return new ProcessorSoundFile(node_id, host_system, desc);
  case pb::ProcessorDescription::MIXER:
    assert(desc.type() == pb::NodeDescription::PROCESSOR);
    return new ProcessorMixer(node_id, host_system, desc);
  case pb::ProcessorDescription::PIANOROLL:
    assert(desc.type() == pb::NodeDescription::PROCESSOR);
    return new ProcessorPianoRoll(node_id, host_system, desc);
  case pb::ProcessorDescription::CV_GENERATOR:
    assert(desc.type() == pb::NodeDescription::PROCESSOR);
    return new ProcessorCVGenerator(node_id, host_system, desc);
  case pb::ProcessorDescription::SAMPLE_SCRIPT:
    assert(desc.type() == pb::NodeDescription::PROCESSOR);
    return new ProcessorSampleScript(node_id, host_system, desc);

  default:
    return ERROR_STATUS("Invalid processor type %d", desc.processor().type());
  }
}

uint64_t Processor::new_id() {
  static mt19937_64 rand(time(0));
  return rand();
}

const char* Processor::state_name(ProcessorState state) {
  switch (state) {
  case ProcessorState::INACTIVE: return "INACTIVE";
  case ProcessorState::SETUP: return "SETUP";
  case ProcessorState::RUNNING: return "RUNNING";
  case ProcessorState::BROKEN: return "BROKEN";
  case ProcessorState::CLEANUP: return "CLEANUP";
  }
  abort();
}

void Processor::set_state(ProcessorState state) {
  if (state == _state) {
    return;
  }

  _logger->info("Processor %llx: State %s -> %s", id(), state_name(_state), state_name(state));
  _state = state;
  state_changed.emit(_state);
}

Status Processor::setup() {
  _logger->info("Processor %llx: Setting up...", id());
  set_state(ProcessorState::SETUP);
  Status status = setup_internal();
  if (status.is_error()) {
    _logger->info("Processor %llx: Setup failed: %s", id(), status.message());
    set_state(ProcessorState::BROKEN);
  } else {
    _logger->info("Processor %llx: Setup complete.", id());
    set_state(ProcessorState::RUNNING);
  }
  return status;
}

Status Processor::setup_internal() {
  _buffers.resize(_desc.ports_size());
  for (int port_idx = 0 ; port_idx < _desc.ports_size() ; ++port_idx) {
    _buffers[port_idx] = nullptr;
  }

  return Status::Ok();
}

void Processor::cleanup() {
  _logger->info("Processor %llx: Cleaning up...", id());
  set_state(ProcessorState::CLEANUP);
  cleanup_internal();
  _logger->info("Processor %llx: Cleanup complete.", id());
  set_state(ProcessorState::INACTIVE);
}

void Processor::cleanup_internal() {
}

Status Processor::handle_message(const string& msg_serialized) {
  unique_ptr<pb::ProcessorMessage> msg(new pb::ProcessorMessage());
  assert(msg->ParseFromString(msg_serialized));
  return handle_message_internal(msg.release());
}

Status Processor::handle_message_internal(pb::ProcessorMessage* msg) {
  unique_ptr<pb::ProcessorMessage> msg_ptr(msg);
  return ERROR_STATUS("Processor %llx: Unhandled message.", id());
}

Status Processor::set_parameters(const string& parameters_serialized) {
  pb::ProcessorParameters parameters;
  assert(parameters.ParseFromString(parameters_serialized));
  _logger->info("Processor %llx: Set parameters:\n%s", id(), parameters.DebugString().c_str());
  return set_parameters_internal(parameters);
}

Status Processor::set_parameters_internal(const pb::ProcessorParameters& parameters) {
  return Status::Ok();
}

void Processor::connect_port(BlockContext* ctxt, uint32_t port_idx, BufferPtr buf) {
  // Some processors might have additional ports, which are not in the NodeDescription.
  if (port_idx < _buffers.size()) {
    _buffers[port_idx] = buf;
  }

  if (state() == ProcessorState::RUNNING) {
    Status status = connect_port_internal(ctxt, port_idx, buf);
    if (status.is_error()) {
      _logger->error(
          "Processor %llx: connect_port(%u) failed: %s", id(), port_idx, status.message());
      set_state(ProcessorState::BROKEN);
    }
  }
}

void Processor::process_block(BlockContext* ctxt, TimeMapper* time_mapper) {
  if (state() == ProcessorState::RUNNING) {
    Status status = process_block_internal(ctxt, time_mapper);
    if (status.is_error()) {
      _logger->error("Processor %llx: process_block() failed: %s", id(), status.message());
      set_state(ProcessorState::BROKEN);
    }
  }

  if (state() != ProcessorState::RUNNING) {
    // Processor is broken, just clear all outputs.
    clear_all_outputs();
  }
}

void Processor::clear_all_outputs() {
  for (int port_idx = 0 ; port_idx < _desc.ports_size() ; ++port_idx) {
    const auto& port = _desc.ports(port_idx);
    if (port.direction() != pb::PortDescription::OUTPUT) {
      continue;
    }

    switch (port.type()) {
    case pb::PortDescription::AUDIO:
    case pb::PortDescription::ARATE_CONTROL: {
      float* buf = (float*)_buffers[port_idx];
      for (uint32_t i = 0 ; i < _host_system->block_size() ; ++i) {
        *buf++ = 0.0;
      }
      break;
    }

    case pb::PortDescription::KRATE_CONTROL: {
      float* buf = (float*)_buffers[port_idx];
      *buf = 0.0;
      break;
    }

    case pb::PortDescription::EVENTS: {
      LV2_Atom_Forge forge;
      lv2_atom_forge_init(&forge, &_host_system->lv2->urid_map);

      LV2_Atom_Forge_Frame frame;
      lv2_atom_forge_set_buffer(&forge, _buffers[port_idx], 10240);

      lv2_atom_forge_sequence_head(&forge, &frame, _host_system->lv2->urid.atom_frame_time);
      lv2_atom_forge_pop(&forge, &frame);
      break;
    }

    default:
      _logger->error("Unsupported port type %d", port.type());
      abort();
    }
  }
}

}  // namespace noisicaa
