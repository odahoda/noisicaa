#include "processor.h"

#include <random>
#include <time.h>

#include "misc.h"
#include "processor_null.h"
#include "processor_ladspa.h"

using namespace std;

namespace noisicaa {

Processor::Processor()
  : _id(Processor::new_id()) {
}

Processor::~Processor() {
  cleanup();
}

Processor* Processor::create(const string& name) {
  if (name == "null") {
    return new ProcessorNull();
  } else if (name == "ladspa") {
    return new ProcessorLadspa();
  } else {
    return nullptr;
  }
}

uint64_t Processor::new_id() {
  static mt19937_64 rand(time(0));
  return rand();
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

Status Processor::setup(const ProcessorSpec* spec) {
  if (_spec.get() != nullptr) {
    return Status::Error(sprintf("Processor %llx already set up.", id()));
  }

  log(LogLevel::INFO, "Setting up processor %llx.", id());
  _spec.reset(spec);

  return Status::Ok();
}

void Processor::cleanup() {
  if (_spec.get() != nullptr) {
    _spec.reset();
    log(LogLevel::INFO, "Processor %llx cleaned up.", id());
  }
}

}  // namespace noisicaa
