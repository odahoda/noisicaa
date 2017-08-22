#include "processor_spec.h"

#include <iostream>
#include "misc.h"

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

Status ProcessorSpec::get_parameter(const string& name, ParameterSpec** param) const {
  const auto& it = _parameters.find(name);
  if (it != _parameters.end()) {
    *param = it->second.get();
    return Status::Ok();
  }

  return Status::Error(sprintf("Parameter '%s' not found.", name.c_str()));
}

}  // namespace noisicaa
