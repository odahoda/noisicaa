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

#include "noisicaa/audioproc/public/processor_message.pb.h"
#include "noisicaa/audioproc/vm/processor.h"
#include "noisicaa/audioproc/vm/processor_null.h"
#include "noisicaa/audioproc/vm/processor_ladspa.h"
#include "noisicaa/audioproc/vm/processor_lv2.h"
#include "noisicaa/audioproc/vm/processor_csound.h"
#include "noisicaa/audioproc/vm/processor_custom_csound.h"
#include "noisicaa/audioproc/vm/processor_sample_player.h"
#include "noisicaa/audioproc/vm/processor_ipc.h"
#include "noisicaa/audioproc/vm/processor_fluidsynth.h"
#include "noisicaa/audioproc/vm/processor_sound_file.h"
#include "noisicaa/audioproc/vm/processor_track_mixer.h"
#include "noisicaa/audioproc/vm/processor_pianoroll.h"
#include "noisicaa/audioproc/vm/processor_cvgenerator.h"
#include "noisicaa/audioproc/vm/processor_sample_script.h"

namespace noisicaa {

Processor::Processor(const string& node_id, const char* logger_name, HostData* host_data)
  : _logger(LoggerRegistry::get_logger(logger_name)),
    _host_data(host_data),
    _id(Processor::new_id()),
    _node_id(node_id) {}

Processor::~Processor() {}

StatusOr<Processor*> Processor::create(
    const string& node_id, HostData* host_data, const string& name) {
  if (name == "null") {
    return new ProcessorNull(node_id, host_data);
  } else if (name == "ladspa") {
    return new ProcessorLadspa(node_id, host_data);
  } else if (name == "lv2") {
    return new ProcessorLV2(node_id, host_data);
  } else if (name == "csound") {
    return new ProcessorCSound(node_id, host_data);
  } else if (name == "custom_csound") {
    return new ProcessorCustomCSound(node_id, host_data);
  } else if (name == "ipc") {
    return new ProcessorIPC(node_id, host_data);
  } else if (name == "fluidsynth") {
    return new ProcessorFluidSynth(node_id, host_data);
  } else if (name == "sample_player") {
    return new ProcessorSamplePlayer(node_id, host_data);
  } else if (name == "sound_file") {
    return new ProcessorSoundFile(node_id, host_data);
  } else if (name == "track_mixer") {
    return new ProcessorTrackMixer(node_id, host_data);
  } else if (name == "pianoroll") {
    return new ProcessorPianoRoll(node_id, host_data);
  } else if (name == "cvgenerator") {
    return new ProcessorCVGenerator(node_id, host_data);
  } else if (name == "sample_script") {
    return new ProcessorSampleScript(node_id, host_data);
  }

  return ERROR_STATUS("Invalid processor name '%s'", name.c_str());
}

uint64_t Processor::new_id() {
  static mt19937_64 rand(time(0));
  return rand();
}

StatusOr<string> Processor::get_string_parameter(const string& name) {
  StatusOr<ParameterSpec*> stor_param_spec = _spec->get_parameter(name);
  RETURN_IF_ERROR(stor_param_spec);

  if (stor_param_spec.result()->type() != ParameterSpec::ParameterType::String) {
    return ERROR_STATUS("Parameter '%s' is not of type string.", name.c_str());
  }

  const auto& it = _string_parameters.find(name);
  if (it != _string_parameters.end()) {
    return it->second;
  }

  StringParameterSpec* param_spec = dynamic_cast<StringParameterSpec*>(
      stor_param_spec.result());
  assert(param_spec != nullptr);

  return param_spec->default_value();
}

Status Processor::set_string_parameter(const string& name, const string& value) {
  // StatusOr<ParameterSpec*> stor_or_param_spec = _spec->get_parameter(name);
  // RETURN_IF_ERROR(stor_or_param_spec);

  // if (stor_or_param_spec.result()->type() != ParameterSpec::ParameterType::String) {
  //   return ERROR_STATUS("Parameter '%s' is not of type string.", name.c_str());
  // }

  _logger->info("Set parameter %s='%s'", name.c_str(), value.c_str());

  _string_parameters[name] = value;
  return Status::Ok();
}

StatusOr<int64_t> Processor::get_int_parameter(const string& name) {
  StatusOr<ParameterSpec*> stor_param_spec = _spec->get_parameter(name);
  RETURN_IF_ERROR(stor_param_spec);

  if (stor_param_spec.result()->type() != ParameterSpec::ParameterType::Int) {
    return ERROR_STATUS("Parameter '%s' is not of type int.", name.c_str());
  }

  const auto& it = _int_parameters.find(name);
  if (it != _int_parameters.end()) {
    return it->second;
  }

  IntParameterSpec* param_spec = dynamic_cast<IntParameterSpec*>(
      stor_param_spec.result());
  assert(param_spec != nullptr);

  return param_spec->default_value();
}

Status Processor::set_int_parameter(const string& name, int64_t value) {
  // StatusOr<ParameterSpec*> stor_param_spec = _spec->get_parameter(name);
  // RETURN_IF_ERROR(stor_param_spec);

  // if (stor_param_spec.result()->type() != ParameterSpec::ParameterType::Int) {
  //   return ERROR_STATUS("Parameter '%s' is not of type string.", name.c_str());
  // }

  _int_parameters[name] = value;
  return Status::Ok();
}

StatusOr<float> Processor::get_float_parameter(const string& name) {
  StatusOr<ParameterSpec*> stor_param_spec = _spec->get_parameter(name);
  RETURN_IF_ERROR(stor_param_spec);

  if (stor_param_spec.result()->type() != ParameterSpec::ParameterType::Float) {
    return ERROR_STATUS("Parameter '%s' is not of type int.", name.c_str());
  }

  const auto& it = _float_parameters.find(name);
  if (it != _float_parameters.end()) {
    return it->second;
  }

  FloatParameterSpec* param_spec = dynamic_cast<FloatParameterSpec*>(
      stor_param_spec.result());
  assert(param_spec != nullptr);

  return param_spec->default_value();
}

Status Processor::set_float_parameter(const string& name, float value) {
  // StatusOr<ParameterSpec*> stor_param_spec = _spec->get_parameter(name);
  // RETURN_IF_ERROR(stor_param_spec);

  // if (stor_param_spec.result()->type() != ParameterSpec::ParameterType::Float) {
  //   return ERROR_STATUS("Parameter '%s' is not of type string.", name.c_str());
  // }

  _int_parameters[name] = value;
  return Status::Ok();
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

Status Processor::setup(const ProcessorSpec* spec) {
  unique_ptr<const ProcessorSpec> spec_ptr(spec);

  if (_spec.get() != nullptr) {
    return ERROR_STATUS("Processor %llx already set up.", id());
  }

  _logger->info("Setting up processor %llx.", id());
  _spec.reset(spec_ptr.release());

  return Status::Ok();
}

void Processor::cleanup() {
  if (_spec.get() != nullptr) {
    _spec.reset();
    _logger->info("Processor %llx cleaned up.", id());
  }
}

}  // namespace noisicaa
