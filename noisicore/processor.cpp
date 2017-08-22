#include "processor.h"

#include "misc.h"
#include "processor_ladspa.h"

namespace noisicaa {

Processor::Processor() {
}

Processor::~Processor() {
  cleanup();
}

Status Processor::get_string_parameter(const string& name, string* value) {
  ParameterSpec* param_spec;
  Status status = _spec->get_parameter(name, &param_spec);
  if (status.is_error()) { return status; }

  if (param_spec->type() != ParameterType::String) {
    return Status::Error(
	 sprintf("Parameter '%s' is not of type string.", name.c_str()));
  }

  StringParameterSpec* string_param_spec =
    dynamic_cast<StringParameterSpec*>(param_spec);
  assert(string_param_spec != nullptr);

  *value = string_param_spec->default_value();
  return Status::Ok();
}

Processor* Processor::create(const string& name) {
  if (name == "ladspa") {
    return new ProcessorLadspa();
  } else {
    return nullptr;
  }
}

Status Processor::setup(const ProcessorSpec* spec) {
  _spec.reset(spec);

  return Status::Ok();
}

void Processor::cleanup() {
  _spec.reset();
}

}  // namespace noisicaa
