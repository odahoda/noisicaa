#include <iostream>
#include "noisicaa/audioproc/vm/processor_spec.h"

namespace noisicaa {

PortSpec::PortSpec(const string& name, PortType type, PortDirection direction)
  : _name(name), _type(type), _direction(direction) {}

ParameterSpec::ParameterSpec(ParameterType type, const string& name)
  : _type(type),
    _name(name) {}
ParameterSpec::~ParameterSpec() {}

StringParameterSpec::StringParameterSpec(
    const string& name, const string& default_value)
  : ParameterSpec(ParameterType::String, name),
    _default_value(default_value) {}

IntParameterSpec::IntParameterSpec(
    const string& name, int64_t default_value)
  : ParameterSpec(ParameterType::Int, name),
    _default_value(default_value) {}

FloatParameterSpec::FloatParameterSpec(
    const string& name, float default_value)
  : ParameterSpec(ParameterType::Float, name),
    _default_value(default_value) {}

ProcessorSpec::ProcessorSpec() {
}

Status ProcessorSpec::add_port(
    const string& name, PortType type, PortDirection direction) {
  _ports.emplace_back(PortSpec(name, type, direction));
  return Status::Ok();
}

Status ProcessorSpec::add_parameter(ParameterSpec* param) {
  _parameters[param->name()].reset(param);
  return Status::Ok();
}

StatusOr<ParameterSpec*> ProcessorSpec::get_parameter(const string& name) const {
  const auto& it = _parameters.find(name);
  if (it != _parameters.end()) {
    return it->second.get();
  }

  return Status::Error("Parameter '%s' not found.", name.c_str());
}

}  // namespace noisicaa
