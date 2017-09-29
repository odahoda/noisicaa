#include "noisicaa/audioproc/vm/control_value.h"

namespace noisicaa {

ControlValue::ControlValue(ControlValueType type, const string& name)
  : _type(type),
    _name(name) {}

ControlValue::~ControlValue() {}

FloatControlValue::FloatControlValue(const string& name, float value)
  : ControlValue(ControlValueType::FloatCV, name),
    _value(value) {}

IntControlValue::IntControlValue(const string& name, int64_t value)
  : ControlValue(ControlValueType::IntCV, name),
    _value(value) {}

}  // namespace noisicaa
