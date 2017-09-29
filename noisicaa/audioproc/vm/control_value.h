// -*- mode: c++ -*-

#ifndef _NOISICAA_AUDIOPROC_VM_CONTROL_VALUE_H
#define _NOISICAA_AUDIOPROC_VM_CONTROL_VALUE_H

#include <string>
#include <stdint.h>

namespace noisicaa {

using namespace std;

enum ControlValueType {
  FloatCV,
  IntCV,
};

class ControlValue {
public:
  virtual ~ControlValue();

  ControlValueType type() const { return _type; }
  const string& name() const { return _name; }

protected:
  ControlValue(ControlValueType type, const string& name);

private:
  ControlValueType _type;
  string _name;
};

class FloatControlValue : public ControlValue {
public:
  FloatControlValue(const string& name, float value);

  float value() const { return _value; }
  void set_value(float value) { _value = value; }

private:
  float _value;
};

class IntControlValue : public ControlValue {
public:
  IntControlValue(const string& name, int64_t value);

  int64_t value() const { return _value; }
  void set_value(int64_t value) { _value = value; }

private:
  int64_t _value;
};

}  // namespace noisicaa

#endif
