#include <random>
#include <time.h>

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

namespace noisicaa {

Processor::Processor(const string& node_id, const char* logger_name, HostData* host_data)
  : _logger(LoggerRegistry::get_logger(logger_name)),
    _host_data(host_data),
    _id(Processor::new_id()),
    _node_id(node_id) {}

Processor::~Processor() {
  cleanup();
}

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
  }

  return Status::Error("Invalid processor name '%s'", name.c_str());
}

uint64_t Processor::new_id() {
  static mt19937_64 rand(time(0));
  return rand();
}

StatusOr<string> Processor::get_string_parameter(const string& name) {
  StatusOr<ParameterSpec*> stor_param_spec = _spec->get_parameter(name);
  if (stor_param_spec.is_error()) { return stor_param_spec; }

  if (stor_param_spec.result()->type() != ParameterSpec::ParameterType::String) {
    return Status::Error("Parameter '%s' is not of type string.", name.c_str());
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
  // if (stor_or_param_spec.is_error()) { return stor_or_param_spec; }

  // if (stor_or_param_spec.result()->type() != ParameterSpec::ParameterType::String) {
  //   return Status::Error("Parameter '%s' is not of type string.", name.c_str());
  // }

  _logger->info("Set parameter %s='%s'", name.c_str(), value.c_str());

  _string_parameters[name] = value;
  return Status::Ok();
}

StatusOr<int64_t> Processor::get_int_parameter(const string& name) {
  StatusOr<ParameterSpec*> stor_param_spec = _spec->get_parameter(name);
  if (stor_param_spec.is_error()) { return stor_param_spec; }

  if (stor_param_spec.result()->type() != ParameterSpec::ParameterType::Int) {
    return Status::Error("Parameter '%s' is not of type int.", name.c_str());
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
  // if (stor_param_spec.is_error()) { return stor_param_spec; }

  // if (stor_param_spec.result()->type() != ParameterSpec::ParameterType::Int) {
  //   return Status::Error("Parameter '%s' is not of type string.", name.c_str());
  // }

  _int_parameters[name] = value;
  return Status::Ok();
}

StatusOr<float> Processor::get_float_parameter(const string& name) {
  StatusOr<ParameterSpec*> stor_param_spec = _spec->get_parameter(name);
  if (stor_param_spec.is_error()) { return stor_param_spec; }

  if (stor_param_spec.result()->type() != ParameterSpec::ParameterType::Float) {
    return Status::Error("Parameter '%s' is not of type int.", name.c_str());
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
  // if (stor_param_spec.is_error()) { return stor_param_spec; }

  // if (stor_param_spec.result()->type() != ParameterSpec::ParameterType::Float) {
  //   return Status::Error("Parameter '%s' is not of type string.", name.c_str());
  // }

  _int_parameters[name] = value;
  return Status::Ok();
}

Status Processor::setup(const ProcessorSpec* spec) {
  unique_ptr<const ProcessorSpec> spec_ptr(spec);

  if (_spec.get() != nullptr) {
    return Status::Error("Processor %llx already set up.", id());
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
